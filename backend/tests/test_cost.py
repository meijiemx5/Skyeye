"""Tests for project cost math.

HZY 2026-08-20: 出库、入库数据需要完整计入项目材料成本。
"""
import pytest

from app.services.cost import budget_status, project_material_cost

STOCK_IN = {"material_id": "m1", "record_type": "in", "quantity": 100, "unit_price": 50}
STOCK_OUT = {"material_id": "m2", "record_type": "out", "quantity": 10, "unit_price": 30}
ADJUSTMENT = {"material_id": "m3", "record_type": "adjustment", "quantity": 5, "unit_price": 20}


# --- 入库 + 出库都计入 ------------------------------------------------------

def test_both_stock_in_and_stock_out_count_toward_material_cost():
    result = project_material_cost([STOCK_IN, STOCK_OUT])
    assert result["material_cost_in"] == 5000.0
    assert result["material_cost_out"] == 300.0
    assert result["material_cost"] == 5300.0


def test_adjustment_records_are_not_project_cost():
    """盘点是库存调整, 不是项目成本。"""
    assert project_material_cost([ADJUSTMENT])["material_cost"] == 0.0
    assert project_material_cost([STOCK_IN, ADJUSTMENT])["material_cost"] == 5000.0


def test_empty_records_produce_zero_cost():
    result = project_material_cost([])
    assert result["material_cost"] == 0.0
    assert result["material_cost_estimated_count"] == 0


def test_multiple_records_of_each_type_accumulate():
    result = project_material_cost([STOCK_IN, STOCK_IN, STOCK_OUT, STOCK_OUT])
    assert result["material_cost_in"] == 10000.0
    assert result["material_cost_out"] == 600.0


# --- 口径切换 ---------------------------------------------------------------

@pytest.mark.parametrize("mode,expected", [
    ("both", 5300.0), ("in", 5000.0), ("out", 300.0),
])
def test_mode_selects_which_side_totals(mode, expected):
    result = project_material_cost([STOCK_IN, STOCK_OUT], mode=mode)
    assert result["material_cost"] == expected
    assert result["material_cost_mode"] == mode
    # 拆分口径始终两边都算出来, 便于对账
    assert result["material_cost_in"] == 5000.0
    assert result["material_cost_out"] == 300.0


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        project_material_cost([STOCK_IN], mode="guess")


# --- 单价回退与估算标记 ------------------------------------------------------

def test_missing_unit_price_falls_back_to_current_material_price():
    record = {"material_id": "m9", "record_type": "out", "quantity": 4, "unit_price": None}
    result = project_material_cost([record], {"m9": 25})
    assert result["material_cost_out"] == 100.0
    assert result["material_cost_estimated_count"] == 1


def test_records_with_their_own_price_are_not_marked_estimated():
    result = project_material_cost([STOCK_IN, STOCK_OUT], {"m1": 999, "m2": 999})
    assert result["material_cost_estimated_count"] == 0
    assert result["material_cost"] == 5300.0


def test_unknown_material_without_price_contributes_zero_and_is_not_flagged():
    """既没有记录单价也查不到物料单价时算 0, 且不谎称"估算"。"""
    record = {"material_id": "ghost", "record_type": "in", "quantity": 4, "unit_price": None}
    result = project_material_cost([record], {})
    assert result["material_cost"] == 0.0
    assert result["material_cost_estimated_count"] == 0


def test_estimated_count_reports_every_fallback_record():
    records = [
        {"material_id": "m1", "record_type": "in", "quantity": 1, "unit_price": None},
        {"material_id": "m1", "record_type": "out", "quantity": 2, "unit_price": None},
    ]
    result = project_material_cost(records, {"m1": 10})
    assert result["material_cost_estimated_count"] == 2
    assert result["material_cost"] == 30.0


# --- 预算 -------------------------------------------------------------------

def test_budget_usage_and_remaining():
    status = budget_status(800000, 612000)
    assert status["usage_rate"] == 76.5
    assert status["remaining_amount"] == 188000.0
    assert status["over_budget"] is False
    assert status["near_budget"] is False
    assert status["has_budget"] is True


def test_over_budget_is_flagged():
    status = budget_status(100000, 120000)
    assert status["over_budget"] is True
    assert status["usage_rate"] == 120.0
    assert status["remaining_amount"] == -20000.0


def test_near_budget_warns_from_ninety_percent():
    assert budget_status(100000, 89999)["near_budget"] is False
    assert budget_status(100000, 90000)["near_budget"] is True
    assert budget_status(100000, 100000)["near_budget"] is True
    # 超支后走 over_budget, 不再算"接近"
    assert budget_status(100000, 100001)["near_budget"] is False


def test_missing_budget_does_not_claim_over_budget():
    status = budget_status(None, 50000)
    assert status["has_budget"] is False
    assert status["over_budget"] is False
    assert status["usage_rate"] == 0.0
