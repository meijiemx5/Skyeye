"""API tests for batched invoicing.

HZY 的原例: 100 万的项目，甲方要求先开 40 万预付款；那 40 万里材料 30 万(13%)、
工费 10 万(9%)，一定是两张发票；剩下的 60 万在另一个时间开 —— 另一个批次。
"""
import pytest

from tests.conftest import seed_contract, seed_project

MATERIAL = {"category": "material", "tax_rate": 13, "amount_with_tax": 300000, "invoice_no": "FP001"}
LABOR = {"category": "construction", "tax_rate": 9, "amount_with_tax": 100000, "invoice_no": "FP002"}


@pytest.fixture
def seeded(store):
    seed_project(store)
    seed_contract(store, contract_id="c1", project_id="p1", contract_type="client", amount=1000000)
    return store


def _create_advance_batch(client):
    res = client.post("/api/invoices/batches", json={
        "contract_id": "c1", "batch_name": "预付款40万", "payment_stage": "advance",
        "issue_date": "2026-03-01", "planned_amount": 400000, "status": "issued",
        "invoices": [MATERIAL, LABOR],
    })
    assert res.status_code == 200, res.text
    return res.json()["data"]["batch_id"]


# --- 批次 + 多张发票 --------------------------------------------------------

def test_one_batch_can_hold_invoices_with_different_tax_rates(seeded, client):
    batch_id = _create_advance_batch(client)
    batch = client.get(f"/api/invoices/batches/{batch_id}").json()["data"]

    assert batch["batch_no"].startswith("FP-")
    assert batch["payment_stage_label"] == "预付款"
    assert batch["invoice_count"] == 2
    assert batch["total_amount_with_tax"] == 400000.0
    assert batch["total_amount_without_tax"] == 357229.85
    assert batch["total_tax_amount"] == 42770.15

    by_no = {i["invoice_no"]: i for i in batch["invoices"]}
    assert by_no["FP001"]["tax_rate"] == 0.13
    assert by_no["FP001"]["amount_without_tax"] == 265486.73
    assert by_no["FP001"]["category_label"] == "材料"
    assert by_no["FP002"]["tax_rate"] == 0.09
    assert by_no["FP002"]["amount_without_tax"] == 91743.12
    assert by_no["FP002"]["category_label"] == "施工"


def test_batch_inherits_contract_and_project_context(seeded, client):
    batch_id = _create_advance_batch(client)
    batch = client.get(f"/api/invoices/batches/{batch_id}").json()["data"]
    assert batch["contract_no"] == "JF-20260101-C1"
    assert batch["project_id"] == "p1"
    assert all(i["project_id"] == "p1" for i in batch["invoices"])


def test_two_batches_at_different_times_are_kept_apart(seeded, client):
    _create_advance_batch(client)
    client.post("/api/invoices/batches", json={
        "contract_id": "c1", "batch_name": "尾款60万", "payment_stage": "final",
        "issue_date": "2026-06-01", "status": "issued",
        "invoices": [{"category": "construction", "tax_rate": 9, "amount_with_tax": 600000}],
    })

    batches = client.get("/api/invoices/batches", params={"contract_id": "c1"}).json()["data"]
    assert [b["batch_name"] for b in batches] == ["尾款60万", "预付款40万"]  # 最新在前
    summary = client.get("/api/invoices/summary", params={"contract_id": "c1"}).json()["data"]
    assert summary["invoiced_amount"] == 1000000.0
    assert summary["fully_invoiced"] is True


# --- 开票进度 ---------------------------------------------------------------

def test_progress_reflects_the_unbilled_remainder(seeded, client):
    _create_advance_batch(client)
    summary = client.get("/api/invoices/summary", params={"contract_id": "c1"}).json()["data"]
    assert summary["contract_amount"] == 1000000.0
    assert summary["invoiced_amount"] == 400000.0
    assert summary["remaining_amount"] == 600000.0
    assert summary["invoiced_rate"] == 40.0
    assert summary["batch_count"] == 1
    assert summary["invoice_count"] == 2
    assert summary["by_category"]["material"]["amount_with_tax"] == 300000.0
    assert set(summary["by_tax_rate"]) == {"13%", "9%"}


def test_voided_batch_is_excluded_from_progress(seeded, client):
    batch_id = _create_advance_batch(client)
    client.put(f"/api/invoices/batches/{batch_id}", json={"status": "void"})
    summary = client.get("/api/invoices/summary", params={"contract_id": "c1"}).json()["data"]
    assert summary["invoiced_amount"] == 0.0
    assert summary["batch_count"] == 0


def test_project_scoped_summary_uses_client_contracts(seeded, client):
    _create_advance_batch(client)
    summary = client.get("/api/invoices/summary", params={"project_id": "p1"}).json()["data"]
    assert summary["contract_amount"] == 1000000.0
    assert summary["invoiced_amount"] == 400000.0


def test_summary_requires_a_scope(seeded, client):
    assert client.get("/api/invoices/summary").status_code == 400


# --- 单张发票的增删改 -------------------------------------------------------

def test_adding_an_invoice_refreshes_the_batch_rollup(seeded, client):
    batch_id = _create_advance_batch(client)
    res = client.post(f"/api/invoices/batches/{batch_id}/items", json={
        "category": "service", "tax_rate": 6, "amount_with_tax": 10600, "invoice_no": "FP003"})
    assert res.status_code == 200

    batch = client.get(f"/api/invoices/batches/{batch_id}").json()["data"]
    assert batch["invoice_count"] == 3
    assert batch["total_amount_with_tax"] == 410600.0


def test_deleting_an_invoice_refreshes_the_batch_rollup(seeded, client):
    batch_id = _create_advance_batch(client)
    invoices = client.get(f"/api/invoices/batches/{batch_id}").json()["data"]["invoices"]
    target = next(i for i in invoices if i["invoice_no"] == "FP002")

    assert client.delete(f"/api/invoices/batches/{batch_id}/items/{target['invoice_id']}").status_code == 200
    batch = client.get(f"/api/invoices/batches/{batch_id}").json()["data"]
    assert batch["invoice_count"] == 1
    assert batch["total_amount_with_tax"] == 300000.0


def test_updating_the_rate_recomputes_the_split(seeded, client):
    batch_id = _create_advance_batch(client)
    invoices = client.get(f"/api/invoices/batches/{batch_id}").json()["data"]["invoices"]
    target = next(i for i in invoices if i["invoice_no"] == "FP001")

    res = client.put(f"/api/invoices/batches/{batch_id}/items/{target['invoice_id']}",
                     json={"tax_rate": 9})
    assert res.status_code == 200
    updated = next(i for i in client.get(f"/api/invoices/batches/{batch_id}").json()["data"]["invoices"]
                   if i["invoice_no"] == "FP001")
    assert updated["tax_rate"] == 0.09
    assert updated["amount_without_tax"] == 275229.36


def test_manual_split_that_does_not_reconcile_is_rejected(seeded, client):
    batch_id = _create_advance_batch(client)
    res = client.post(f"/api/invoices/batches/{batch_id}/items", json={
        "category": "material", "tax_rate": 13, "amount_with_tax": 1130,
        "amount_without_tax": 500, "tax_amount": 130})
    assert res.status_code == 400
    assert "金额校验失败" in res.json()["detail"]


def test_zero_amount_invoice_is_rejected(seeded, client):
    batch_id = _create_advance_batch(client)
    res = client.post(f"/api/invoices/batches/{batch_id}/items",
                      json={"category": "material", "tax_rate": 13, "amount_with_tax": 0})
    assert res.status_code == 400


def test_deleting_a_batch_removes_its_invoices(seeded, client):
    batch_id = _create_advance_batch(client)
    assert client.delete(f"/api/invoices/batches/{batch_id}").status_code == 200
    assert client.get(f"/api/invoices/batches/{batch_id}").status_code == 404
    summary = client.get("/api/invoices/summary", params={"contract_id": "c1"}).json()["data"]
    assert summary["invoice_count"] == 0


def test_batch_needs_an_existing_contract(seeded, client):
    res = client.post("/api/invoices/batches", json={"contract_id": "nope"})
    assert res.status_code == 400
    assert "关联合同不存在" in res.json()["detail"]


# --- 权限 -------------------------------------------------------------------

def test_finance_can_manage_invoices(seeded, as_user):
    finance = as_user("finance")
    res = finance.post("/api/invoices/batches", json={
        "contract_id": "c1", "payment_stage": "advance", "invoices": [MATERIAL]})
    assert res.status_code == 200


def test_project_manager_can_view_but_not_manage(seeded, as_user, client):
    _create_advance_batch(client)
    pm = as_user("pm")
    assert pm.get("/api/invoices/batches").status_code == 200
    assert pm.post("/api/invoices/batches", json={"contract_id": "c1"}).status_code == 403


@pytest.mark.parametrize("role", ["procurement", "construction", "warehouse"])
def test_field_roles_cannot_see_invoices(seeded, as_user, role):
    assert as_user(role).get("/api/invoices/batches").status_code == 403
