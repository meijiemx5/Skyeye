"""Tests for invoice tax math and batch rollups.

HZY 的例子: 100 万项目, 甲方先要 40 万预付款发票, 其中材料 30 万(13%)、
工费 10 万(9%) —— 一个批次两张发票; 剩下 60 万另一时间开。
"""
import pytest

from app.services import invoice_calc as calc


# --- 税率归一化 -------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    (13, 0.13), (13.0, 0.13), (0.13, 0.13),
    (9, 0.09), (6, 0.06), (3, 0.03), (1, 0.01),
    (0, 0.0), (None, 0.0),
])
def test_normalize_accepts_percent_or_fraction(raw, expected):
    assert calc.normalize_tax_rate(raw) == pytest.approx(expected)


def test_normalize_rejects_negative_and_absurd_rates():
    with pytest.raises(calc.InvoiceAmountError):
        calc.normalize_tax_rate(-1)
    with pytest.raises(calc.InvoiceAmountError):
        calc.normalize_tax_rate(500)


def test_default_rates_follow_chinese_vat_categories():
    assert calc.default_rate_for("material") == 0.13
    assert calc.default_rate_for("construction") == 0.09
    assert calc.default_rate_for("service") == 0.06
    assert calc.default_rate_for("other") == 0.0
    assert calc.default_rate_for("unknown-category") == 0.0


# --- 含税 → 不含税 + 税额 ---------------------------------------------------

def test_material_invoice_at_13_percent():
    without_tax, tax = calc.split_amount(300000, 13)
    assert without_tax == 265486.73
    assert tax == 34513.27
    assert round(without_tax + tax, 2) == 300000.00


def test_labor_invoice_at_9_percent():
    without_tax, tax = calc.split_amount(100000, 9)
    assert without_tax == 91743.12
    assert tax == 8256.88
    assert round(without_tax + tax, 2) == 100000.00


def test_zero_rate_leaves_no_tax():
    assert calc.split_amount(1000, 0) == (1000.0, 0.0)


def test_split_is_consistent_whether_rate_is_percent_or_fraction():
    assert calc.split_amount(50000, 6) == calc.split_amount(50000, 0.06)


# --- resolve_amounts: 自动换算与手工覆盖 ------------------------------------

def test_resolve_derives_missing_amounts():
    result = calc.resolve_amounts(300000, 13)
    assert result == {
        "amount_with_tax": 300000.0,
        "amount_without_tax": 265486.73,
        "tax_amount": 34513.27,
        "tax_rate": 0.13,
    }


def test_resolve_keeps_manual_override_within_tolerance():
    """发票上印的数字才是准的, 允许手工覆盖。"""
    result = calc.resolve_amounts(300000, 13, amount_without_tax=265486.72, tax_amount=34513.28)
    assert result["amount_without_tax"] == 265486.72
    assert result["tax_amount"] == 34513.28


def test_resolve_rejects_override_that_does_not_reconcile():
    with pytest.raises(calc.InvoiceAmountError) as exc:
        calc.resolve_amounts(300000, 13, amount_without_tax=200000, tax_amount=34513.27)
    assert "金额校验失败" in str(exc.value)


def test_resolve_fills_the_other_half_of_a_partial_override():
    assert calc.resolve_amounts(1130, 13, tax_amount=130)["amount_without_tax"] == 1000.0
    assert calc.resolve_amounts(1130, 13, amount_without_tax=1000)["tax_amount"] == 130.0


def test_resolve_rejects_non_positive_total():
    for bad in (0, -100, None):
        with pytest.raises(calc.InvoiceAmountError):
            calc.resolve_amounts(bad, 13)


def test_resolve_rejects_negative_components():
    with pytest.raises(calc.InvoiceAmountError):
        calc.resolve_amounts(1000, 0, amount_without_tax=1200, tax_amount=-200)


# --- 批次汇总: 一个批次多张不同税率的发票 -----------------------------------

def _advance_batch():
    """HZY 的 40 万预付款批次: 材料 30 万 + 工费 10 万。"""
    return [
        {**calc.resolve_amounts(300000, 13), "category": "material"},
        {**calc.resolve_amounts(100000, 9), "category": "construction"},
    ]


def test_batch_totals_sum_the_two_invoices():
    totals = calc.batch_totals(_advance_batch())
    assert totals["invoice_count"] == 2
    assert totals["total_amount_with_tax"] == 400000.0
    assert totals["total_amount_without_tax"] == 357229.85
    assert totals["total_tax_amount"] == 42770.15
    assert round(totals["total_amount_without_tax"] + totals["total_tax_amount"], 2) == 400000.0


def test_empty_batch_totals_are_zero():
    assert calc.batch_totals([]) == {
        "invoice_count": 0, "total_amount_with_tax": 0.0,
        "total_amount_without_tax": 0.0, "total_tax_amount": 0.0,
    }


def test_group_by_category_and_tax_rate():
    items = _advance_batch()
    by_category = calc.group_amounts(items, "category")
    assert by_category["material"]["amount_with_tax"] == 300000.0
    assert by_category["construction"]["amount_with_tax"] == 100000.0

    by_rate = calc.group_amounts(items, "tax_rate")
    assert set(by_rate) == {"13%", "9%"}
    assert by_rate["13%"]["count"] == 1


# --- 开票进度 ---------------------------------------------------------------

def test_progress_after_the_advance_batch_only():
    progress = calc.invoice_progress(1000000, _advance_batch())
    assert progress["invoiced_amount"] == 400000.0
    assert progress["remaining_amount"] == 600000.0
    assert progress["invoiced_rate"] == 40.0
    assert progress["fully_invoiced"] is False


def test_progress_is_complete_once_the_rest_is_invoiced():
    items = _advance_batch() + [{**calc.resolve_amounts(600000, 9), "category": "construction"}]
    progress = calc.invoice_progress(1000000, items)
    assert progress["invoiced_amount"] == 1000000.0
    assert progress["remaining_amount"] == 0.0
    assert progress["fully_invoiced"] is True


def test_progress_tolerates_rounding_dust():
    progress = calc.invoice_progress(1000, [{"amount_with_tax": 999.99}])
    assert progress["fully_invoiced"] is True


def test_progress_without_a_contract_amount_is_not_complete():
    progress = calc.invoice_progress(0, [])
    assert progress["invoiced_rate"] == 0.0
    assert progress["fully_invoiced"] is False


def test_progress_can_report_over_invoicing():
    progress = calc.invoice_progress(1000, [{"amount_with_tax": 1200}])
    assert progress["remaining_amount"] == -200.0
    assert progress["invoiced_rate"] == 120.0
