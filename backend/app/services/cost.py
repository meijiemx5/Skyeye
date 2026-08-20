"""Project cost math.

Pure functions over plain dicts so the costing rules are testable without AWS.
"""

# 材料成本口径:
#   in   仅项目直采入库
#   out  仅项目领用出库
#   both 两者都计入（HZY 2026-08-20：出入库需完整计入项目材料成本）
MATERIAL_COST_MODES = ("both", "in", "out")


def _record_cost(record: dict, material_prices: dict | None) -> tuple[float, bool]:
    """(金额, 是否用了回退单价) for one stock record."""
    quantity = float(record.get("quantity") or 0)
    unit_price = record.get("unit_price")
    estimated = False
    if not unit_price:
        unit_price = (material_prices or {}).get(record.get("material_id"), 0)
        estimated = bool(quantity) and bool(unit_price)
    return round(quantity * float(unit_price or 0), 2), estimated


def project_material_cost(stock_records, material_prices: dict | None = None, mode: str = "both") -> dict:
    """材料成本, split by 入库 / 出库.

    `stock_records` must already be filtered to one project. Records without a
    unit price fall back to the material's current price and are counted in
    `estimated_count`, so an "exact" number never hides a guess.
    """
    if mode not in MATERIAL_COST_MODES:
        raise ValueError(f"未知的材料成本口径: {mode}")

    cost_in = cost_out = 0.0
    estimated = 0
    for record in stock_records:
        record_type = record.get("record_type")
        if record_type not in ("in", "out"):
            continue  # 盘点(adjustment) 不是项目成本
        amount, is_estimated = _record_cost(record, material_prices)
        if is_estimated:
            estimated += 1
        if record_type == "in":
            cost_in += amount
        else:
            cost_out += amount

    cost_in, cost_out = round(cost_in, 2), round(cost_out, 2)
    total = {"both": cost_in + cost_out, "in": cost_in, "out": cost_out}[mode]
    return {
        "material_cost": round(total, 2),
        "material_cost_in": cost_in,
        "material_cost_out": cost_out,
        "material_cost_estimated_count": estimated,
        "material_cost_mode": mode,
    }


def budget_status(budget_amount, used_amount, warning_rate: float = 90.0) -> dict:
    """预算使用情况; `warning_rate` 是亮黄灯的使用率阈值(%)。"""
    budget = round(float(budget_amount or 0), 2)
    used = round(float(used_amount or 0), 2)
    # 阈值判断用未四舍五入的比率，否则 89.999% 会被读成 90%
    raw_rate = used / budget * 100 if budget > 0 else 0.0
    return {
        "budget_amount": budget,
        "used_amount": used,
        "remaining_amount": round(budget - used, 2) if budget > 0 else 0.0,
        "usage_rate": round(raw_rate, 2),
        "over_budget": budget > 0 and used > budget,
        "near_budget": budget > 0 and warning_rate <= raw_rate <= 100,
        "has_budget": budget > 0,
    }
