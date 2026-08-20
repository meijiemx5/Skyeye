"""API tests for project cost analysis.

HZY 2026-08-20: 支持项目成本分析，出库、入库数据需要完整计入项目材料成本。
"""
import pytest

from tests.conftest import seed_contract, seed_material, seed_project, seed_stock_record


@pytest.fixture
def seeded(store):
    seed_project(store, project_id="p1", budget_amount=800000, quote_amount=950000)
    seed_contract(store, contract_id="c1", contract_type="client", amount=1000000, paid_amount=400000)
    seed_contract(store, contract_id="c2", contract_type="supplier", amount=300000, paid_amount=100000)
    seed_contract(store, contract_id="c3", contract_type="construction", amount=100000)
    seed_material(store, material_id="m1", unit_price=50)
    return store


def _analysis(client, **params):
    res = client.get("/api/analysis/project/p1", params=params)
    assert res.status_code == 200, res.text
    return res.json()["data"]


# --- 材料成本: 入库 + 出库都计入 --------------------------------------------

def test_stock_in_and_stock_out_both_count(seeded, client):
    seed_stock_record(seeded, record_id="s1", record_type="in", quantity=100, unit_price=50)
    seed_stock_record(seeded, record_id="s2", record_type="out", quantity=10, unit_price=30)

    cost = _analysis(client)["cost"]
    assert cost["material_cost_in"] == 5000.0
    assert cost["material_cost_out"] == 300.0
    assert cost["material_cost"] == 5300.0
    assert cost["material_cost_mode"] == "both"


def test_stock_records_of_other_projects_are_excluded(seeded, client):
    seed_stock_record(seeded, record_id="s1", record_type="in", quantity=100, unit_price=50)
    seed_stock_record(seeded, record_id="s9", record_type="in", quantity=999,
                      unit_price=99, project_id="p-other")

    assert _analysis(client)["cost"]["material_cost"] == 5000.0


def test_stocktake_adjustments_are_not_project_cost(seeded, client):
    seed_stock_record(seeded, record_id="s1", record_type="adjustment", quantity=5, unit_price=50)
    assert _analysis(client)["cost"]["material_cost"] == 0.0


def test_records_without_a_price_fall_back_and_are_flagged(seeded, client):
    seed_stock_record(seeded, record_id="s1", record_type="out", quantity=4, unit_price=None)
    cost = _analysis(client)["cost"]
    assert cost["material_cost_out"] == 200.0                  # 回退到物料当前单价 50
    assert cost["material_cost_estimated_count"] == 1


@pytest.mark.parametrize("mode,expected", [("both", 5300.0), ("in", 5000.0), ("out", 300.0)])
def test_material_cost_mode_can_be_switched(seeded, client, mode, expected):
    seed_stock_record(seeded, record_id="s1", record_type="in", quantity=100, unit_price=50)
    seed_stock_record(seeded, record_id="s2", record_type="out", quantity=10, unit_price=30)
    assert _analysis(client, material_cost_mode=mode)["cost"]["material_cost"] == expected


def test_unknown_mode_falls_back_to_both(seeded, client):
    seed_stock_record(seeded, record_id="s1", record_type="in", quantity=100, unit_price=50)
    assert _analysis(client, material_cost_mode="guess")["cost"]["material_cost_mode"] == "both"


# --- 总成本 / 利润 / 预算 ---------------------------------------------------

def test_material_cost_is_part_of_total_cost_and_profit(seeded, client):
    seed_stock_record(seeded, record_id="s1", record_type="in", quantity=100, unit_price=50)
    seed_stock_record(seeded, record_id="s2", record_type="out", quantity=10, unit_price=30)

    data = _analysis(client)
    # 采购 300000 + 施工 100000 + 报销 0 + 材料 5300
    assert data["cost"]["total_cost"] == 405300.0
    assert data["profit"]["profit"] == 594700.0
    assert data["cost"]["cost_breakdown"]["material_pct"] == pytest.approx(1.307, abs=0.01)


def test_budget_block_tracks_usage_against_total_cost(seeded, client):
    data = _analysis(client)
    assert data["budget"]["budget_amount"] == 800000.0
    assert data["budget"]["quote_amount"] == 950000.0
    assert data["budget"]["used_amount"] == 400000.0
    assert data["budget"]["usage_rate"] == 50.0
    assert data["budget"]["over_budget"] is False


def test_over_budget_is_reported(store, client):
    seed_project(store, project_id="p1", budget_amount=100000)
    seed_contract(store, contract_id="c2", contract_type="supplier", amount=300000)
    data = _analysis(client)
    assert data["budget"]["over_budget"] is True


def test_project_without_budget_does_not_claim_over_budget(store, client):
    seed_project(store, project_id="p1")
    seed_contract(store, contract_id="c2", contract_type="supplier", amount=300000)
    budget = _analysis(client)["budget"]
    assert budget["has_budget"] is False
    assert budget["over_budget"] is False


# --- 开票进度嵌入项目分析 ---------------------------------------------------

def test_analysis_includes_invoice_progress(seeded, client):
    client.post("/api/invoices/batches", json={
        "contract_id": "c1", "payment_stage": "advance", "status": "issued",
        "invoices": [
            {"category": "material", "tax_rate": 13, "amount_with_tax": 300000},
            {"category": "construction", "tax_rate": 9, "amount_with_tax": 100000},
        ]})

    progress = _analysis(client)["invoice_progress"]
    assert progress["contract_amount"] == 1000000.0
    assert progress["invoiced_amount"] == 400000.0
    assert progress["remaining_amount"] == 600000.0
    assert progress["fully_invoiced"] is False


def test_analysis_without_invoices_reports_zero_progress(seeded, client):
    progress = _analysis(client)["invoice_progress"]
    assert progress["invoiced_amount"] == 0.0
    assert progress["fully_invoiced"] is False


# --- 总览 -------------------------------------------------------------------

def test_overview_includes_material_cost_and_budget_flag(seeded, client):
    seed_stock_record(seeded, record_id="s1", record_type="in", quantity=100, unit_price=50)
    data = client.get("/api/analysis/overview").json()["data"]
    project = data["projects"][0]
    assert project["cost"] == 405000.0
    assert project["budget_amount"] == 800000.0
    assert project["over_budget"] is False


@pytest.mark.parametrize("role", ["procurement", "construction", "warehouse"])
def test_overview_is_restricted(seeded, as_user, role):
    assert as_user(role).get("/api/analysis/overview").status_code == 403


def test_overview_for_project_manager_covers_only_their_projects(store, as_user):
    seed_project(store, project_id="p1", manager_id="u-pm")
    seed_project(store, project_id="p2", manager_id="u-other")
    seed_contract(store, contract_id="c9", project_id="p2", contract_type="client", amount=500000)

    data = as_user("pm").get("/api/analysis/overview").json()["data"]
    assert [p["project_id"] for p in data["projects"]] == ["p1"]
    assert data["summary"]["total_revenue"] == 0
