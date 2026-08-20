"""Invoice tax math and batch aggregation.

Pure functions — no DynamoDB, no FastAPI. Invoices are entered with the
tax-inclusive amount plus a tax rate; the other two numbers are derived but may
be overridden, because whatever is printed on the paper invoice wins.
"""

# 发票类别 → 默认税率（仅表单预填；小规模纳税人/简易计税会不同，以录入值为准）
CATEGORY_DEFAULT_RATES = {
    "material": 0.13,      # 材料/货物
    "construction": 0.09,  # 施工/建筑服务
    "service": 0.06,       # 技术服务
    "other": 0.0,          # 其他（3% / 1% / 免税等手填）
}

CATEGORY_LABELS = {
    "material": "材料",
    "construction": "施工",
    "service": "技术服务",
    "other": "其他",
}

PAYMENT_STAGE_LABELS = {
    "advance": "预付款",
    "progress": "进度款",
    "final": "尾款",
    "other": "其他",
}

BATCH_STATUS_LABELS = {
    "draft": "待开票",
    "issued": "已开票",
    "received": "甲方已收",
    "void": "已作废",
}

# Rounding slack when the client sends its own without-tax / tax split.
AMOUNT_TOLERANCE = 0.02


class InvoiceAmountError(Exception):
    """Raised when the three amounts on an invoice do not add up."""


def normalize_tax_rate(value) -> float:
    """Accept 13, 13.0 or 0.13 and return the fraction (0.13).

    The UI talks in percent, storage keeps fractions. Values >= 1 are read as
    percent — no real VAT rate is 100%, while 1% and 3% (小规模纳税人) are common,
    so `1` must mean 1% rather than 100%.
    """
    if value is None:
        return 0.0
    rate = float(value)
    if rate < 0:
        raise InvoiceAmountError("税率不能为负数")
    if rate >= 1:
        rate = rate / 100.0
    if rate > 1:
        raise InvoiceAmountError("税率不合法")
    return round(rate, 6)


def default_rate_for(category: str) -> float:
    return CATEGORY_DEFAULT_RATES.get(category, 0.0)


def split_amount(amount_with_tax, tax_rate) -> tuple[float, float]:
    """(不含税金额, 税额) derived from the tax-inclusive amount and rate."""
    total = round(float(amount_with_tax or 0), 2)
    rate = normalize_tax_rate(tax_rate)
    without_tax = round(total / (1 + rate), 2)
    return without_tax, round(total - without_tax, 2)


def resolve_amounts(amount_with_tax, tax_rate, amount_without_tax=None, tax_amount=None) -> dict:
    """Final three amounts for one invoice, honouring manual overrides.

    Overrides are kept only if they reconcile within AMOUNT_TOLERANCE, so a
    typo cannot silently corrupt the books.
    """
    total = round(float(amount_with_tax or 0), 2)
    if total <= 0:
        raise InvoiceAmountError("发票含税金额必须大于0")
    rate = normalize_tax_rate(tax_rate)

    if amount_without_tax is None and tax_amount is None:
        without_tax, tax = split_amount(total, rate)
    else:
        if amount_without_tax is None:
            without_tax = round(total - float(tax_amount), 2)
            tax = round(float(tax_amount), 2)
        elif tax_amount is None:
            without_tax = round(float(amount_without_tax), 2)
            tax = round(total - without_tax, 2)
        else:
            without_tax = round(float(amount_without_tax), 2)
            tax = round(float(tax_amount), 2)
        if abs(without_tax + tax - total) > AMOUNT_TOLERANCE:
            raise InvoiceAmountError(
                f"金额校验失败: 不含税({without_tax}) + 税额({tax}) 与含税({total}) 不符"
            )
        if without_tax < 0 or tax < 0:
            raise InvoiceAmountError("不含税金额与税额不能为负数")

    return {
        "amount_with_tax": total,
        "amount_without_tax": without_tax,
        "tax_amount": tax,
        "tax_rate": rate,
    }


def batch_totals(items) -> dict:
    """Roll a batch's invoices up into the totals stored on the batch."""
    return {
        "invoice_count": len(items),
        "total_amount_with_tax": round(sum(float(i.get("amount_with_tax") or 0) for i in items), 2),
        "total_amount_without_tax": round(sum(float(i.get("amount_without_tax") or 0) for i in items), 2),
        "total_tax_amount": round(sum(float(i.get("tax_amount") or 0) for i in items), 2),
    }


def group_amounts(items, key: str) -> dict:
    """Group invoice amounts by `category` or `tax_rate` for the summary view."""
    grouped: dict[str, dict] = {}
    for item in items:
        raw = item.get(key)
        bucket = f"{normalize_tax_rate(raw) * 100:g}%" if key == "tax_rate" else (raw or "other")
        entry = grouped.setdefault(str(bucket), {"count": 0, "amount_with_tax": 0.0, "tax_amount": 0.0})
        entry["count"] += 1
        entry["amount_with_tax"] = round(entry["amount_with_tax"] + float(item.get("amount_with_tax") or 0), 2)
        entry["tax_amount"] = round(entry["tax_amount"] + float(item.get("tax_amount") or 0), 2)
    return grouped


def invoice_progress(contract_amount, items) -> dict:
    """开票进度 against a contract amount (voided batches excluded upstream)."""
    total = round(float(contract_amount or 0), 2)
    invoiced = round(sum(float(i.get("amount_with_tax") or 0) for i in items), 2)
    remaining = round(total - invoiced, 2)
    return {
        "contract_amount": total,
        "invoiced_amount": invoiced,
        "remaining_amount": remaining,
        "invoiced_rate": round(invoiced / total * 100, 2) if total > 0 else 0.0,
        "fully_invoiced": total > 0 and remaining <= AMOUNT_TOLERANCE,
        "by_category": group_amounts(items, "category"),
        "by_tax_rate": group_amounts(items, "tax_rate"),
    }
