"""API tests for the project alert board and the todo centre.

不断言具体逾期天数（那会随真实日期漂移），只断言状态、归属与聚合 —— 天数计算由
tests/test_alerts.py 用固定的 today 覆盖。
"""
import pytest

from tests.conftest import seed_category, seed_contract, seed_project

# 项目起止日期都在过去，所以未完成项一定是 overdue 而不是 missing
PAST = {"start_date": "2026-01-01", "end_date": "2026-06-30"}


@pytest.fixture
def bare_project(store):
    """一个什么都没有的项目：预算、报价、合同、验收全缺。"""
    seed_project(store, project_id="p1", name="某小区弱电", manager_id="u-pm", **PAST)
    return store


@pytest.fixture
def furnished_project(store, client):
    """预算/报价/三类合同/发票齐全的项目。"""
    seed_project(store, project_id="p1", name="某小区弱电", manager_id="u-pm",
                 budget_amount=800000, quote_amount=950000, **PAST)
    seed_contract(store, contract_id="c1", contract_type="client", amount=1000000)
    seed_contract(store, contract_id="c2", contract_type="supplier", amount=300000)
    seed_contract(store, contract_id="c3", contract_type="construction", amount=100000)
    client.post("/api/invoices/batches", json={
        "contract_id": "c1", "payment_stage": "advance", "status": "issued",
        "invoices": [{"category": "material", "tax_rate": 13, "amount_with_tax": 1000000}],
    })
    return store


def _items(board_project):
    return {item["key"]: item for item in board_project["items"]}


# --- 看板 -------------------------------------------------------------------

def test_board_flags_every_missing_part_of_a_bare_project(bare_project, client):
    board = client.get("/api/alerts/board").json()["data"]
    assert board["summary"]["project_count"] == 1
    project = board["projects"][0]
    items = _items(project)

    for key in ("budget", "quote", "client_contract", "labor_contract", "acceptance"):
        assert items[key]["status"] == "overdue", key
    assert items["supplier_contract"]["applicable"] is False  # 没有材料成本
    assert items["invoice"]["applicable"] is False            # 没有甲方合同金额
    assert project["health_score"] < 20
    assert board["summary"]["overdue_items"] == 5


def test_board_reports_the_eight_checklist_keys(bare_project, client):
    board = client.get("/api/alerts/board").json()["data"]
    assert board["checklist_keys"] == [
        "budget", "quote", "client_contract", "supplier_contract",
        "labor_contract", "acceptance", "invoice", "reimbursement"]


def test_furnished_project_only_misses_the_acceptance_documents(furnished_project, client):
    project = client.get("/api/alerts/board").json()["data"]["projects"][0]
    items = _items(project)
    assert items["budget"]["status"] == "ok"
    assert items["quote"]["status"] == "ok"
    assert items["client_contract"]["status"] == "ok"
    assert items["labor_contract"]["status"] == "ok"
    assert items["invoice"]["status"] == "ok"           # 100 万已开完
    assert items["acceptance"]["status"] == "overdue"   # 还没传验收资料
    assert items["acceptance"]["owner_id"] == "u-pm"


def test_partial_invoicing_lights_up_the_invoice_item(store, client):
    seed_project(store, project_id="p1", budget_amount=800000, quote_amount=950000, **PAST)
    seed_contract(store, contract_id="c1", contract_type="client", amount=1000000)
    client.post("/api/invoices/batches", json={
        "contract_id": "c1", "payment_stage": "advance", "status": "issued",
        "invoices": [{"category": "material", "tax_rate": 13, "amount_with_tax": 400000}]})

    item = _items(client.get("/api/alerts/board").json()["data"]["projects"][0])["invoice"]
    assert item["status"] == "overdue"
    assert item["owner_role"] == "finance"
    assert "600,000" in item["message"]


def test_board_filters_by_project_status(store, client):
    seed_project(store, project_id="p1", name="进行中", status="active", **PAST)
    seed_project(store, project_id="p2", name="已完成", status="completed", **PAST)

    active = client.get("/api/alerts/board").json()["data"]
    assert [p["project_id"] for p in active["projects"]] == ["p1"]
    every = client.get("/api/alerts/board", params={"project_status": "all"}).json()["data"]
    assert {p["project_id"] for p in every["projects"]} == {"p1", "p2"}


def test_project_manager_board_is_limited_to_their_projects(store, as_user):
    seed_project(store, project_id="p1", manager_id="u-pm", **PAST)
    seed_project(store, project_id="p2", manager_id="u-other", **PAST)

    board = as_user("pm").get("/api/alerts/board").json()["data"]
    assert [p["project_id"] for p in board["projects"]] == ["p1"]


@pytest.mark.parametrize("role", ["procurement", "construction", "warehouse"])
def test_board_is_closed_to_roles_without_project_visibility(bare_project, as_user, role):
    """看板文案里带预算/合同金额，不能对这些角色开放；但待办仍然要能看。"""
    user = as_user(role)
    assert user.get("/api/alerts/board").status_code == 403
    assert user.get("/api/alerts/project/p1").status_code == 403
    assert user.get("/api/todos").status_code == 200
    assert user.get("/api/todos/count").status_code == 200


def test_procurement_still_gets_its_own_todo_from_the_checklist(store, as_user, client):
    """采购看不到看板，但"该项目缺采购合同"这条待办要送到他手上。"""
    from tests.conftest import seed_material, seed_stock_record
    seed_project(store, project_id="p1", manager_id="u-pm", **PAST)
    seed_material(store)
    seed_stock_record(store, record_type="in", quantity=100, unit_price=50)

    todos = as_user("procurement").get("/api/todos").json()["data"]["todos"]
    assert [t["todo_id"].split(":")[-1] for t in todos] == ["supplier_contract"]


@pytest.mark.parametrize("role", ["admin", "finance", "pm"])
def test_board_open_to_admin_finance_and_pm(bare_project, as_user, role):
    assert as_user(role).get("/api/alerts/board").status_code == 200


def test_single_project_checklist_endpoint(bare_project, client):
    data = client.get("/api/alerts/project/p1").json()["data"]
    assert data["project_id"] == "p1"
    assert len(data["items"]) == 8


def test_single_project_checklist_hides_other_peoples_projects(store, as_user):
    seed_project(store, project_id="p2", manager_id="u-other", **PAST)
    assert as_user("pm").get("/api/alerts/project/p2").status_code == 404


# --- 待办 -------------------------------------------------------------------

def test_project_manager_gets_their_projects_unfinished_items(bare_project, as_user):
    data = as_user("pm").get("/api/todos").json()["data"]
    keys = {t["todo_id"].split(":")[-1] for t in data["todos"]}
    assert keys == {"budget", "quote", "client_contract", "labor_contract", "acceptance"}
    assert data["summary"]["by_type"]["project_checklist"] == 5
    assert all(t["link"] == "/projects/p1" for t in data["todos"])


def test_todos_are_sorted_most_urgent_first(bare_project, as_user):
    todos = as_user("pm").get("/api/todos").json()["data"]["todos"]
    severities = [t["severity"] for t in todos]
    assert severities == sorted(severities, key=lambda s: {"high": 0, "medium": 1, "low": 2}[s])


def test_unrelated_project_manager_has_nothing_to_do(bare_project, as_user):
    store_user = as_user("construction")
    assert store_user.get("/api/todos").json()["data"]["todos"] == []


def test_pending_reimbursement_shows_up_for_the_reviewer(store, as_user):
    seed_project(store, project_id="p1", manager_id="u-pm", **PAST)
    seed_category(store)
    seed_contract(store, contract_id="c1", contract_type="client")
    admin = as_user("admin")
    admin.post("/api/reimbursements", json={
        "project_id": "p1", "project_name": "某小区弱电", "amount_with_tax": 1200,
        "expense_type": "cat-material", "expense_category_id": "cat-material",
        "description": "买线材", "expense_date": "2026-08-01"})

    pm_todos = as_user("pm").get("/api/todos").json()["data"]["todos"]
    reimburse = [t for t in pm_todos if t["type"] == "reimbursement"]
    assert len(reimburse) == 1
    assert "待主管审核" in reimburse[0]["title"]
    assert reimburse[0]["link"] == "/reimbursements"

    # 财务此刻还没事做（要等主管审完）
    finance_todos = as_user("finance").get("/api/todos").json()["data"]["todos"]
    assert [t for t in finance_todos if t["type"] == "reimbursement"] == []


def test_receipt_confirmation_lands_on_finance(store, as_user):
    seed_project(store, project_id="p1", manager_id="u-pm", **PAST)
    seed_category(store)
    seed_contract(store, contract_id="c1", contract_type="client")
    admin = as_user("admin")
    rid = admin.post("/api/reimbursements", json={
        "project_id": "p1", "project_name": "某小区弱电", "amount_with_tax": 1200,
        "expense_type": "cat-material", "expense_category_id": "cat-material",
        "description": "买线材", "expense_date": "2026-08-01"}).json()["data"]["reimburse_id"]
    admin.post(f"/api/reimbursements/{rid}/audit", json={"action": "approved"})

    todos = as_user("finance").get("/api/todos").json()["data"]["todos"]
    assert any("待确认项目收款" in t["title"] for t in todos)


def test_reimbursement_todos_are_scoped_to_the_managers_own_projects(store, as_user):
    """别人项目上的报销不该出现在我的待办里 —— 点进去我也看不到那条记录。"""
    seed_project(store, project_id="p1", manager_id="u-pm", **PAST)
    seed_project(store, project_id="p2", manager_id="u-other", **PAST)
    seed_category(store)
    worker = as_user("construction")
    for pid in ("p1", "p2"):
        worker.post("/api/reimbursements", json={
            "project_id": pid, "project_name": pid, "amount_with_tax": 100,
            "expense_type": "cat-material", "expense_category_id": "cat-material",
            "description": "买线材", "expense_date": "2026-08-01"})

    todos = as_user("pm").get("/api/todos").json()["data"]["todos"]
    reimburse = [t for t in todos if t["type"] == "reimbursement"]
    assert len(reimburse) == 1
    assert reimburse[0]["project_id"] == "p1"


def test_todo_count_is_a_lightweight_summary(bare_project, as_user):
    data = as_user("pm").get("/api/todos/count").json()["data"]
    assert data["total"] == 5
    assert set(data) == {"total", "high", "medium", "low", "by_type"}


def test_todos_can_be_filtered_by_type_and_severity(bare_project, as_user):
    pm = as_user("pm")
    by_type = pm.get("/api/todos", params={"todo_type": "stock_warning"}).json()
    assert by_type["data"]["todos"] == []
    # summary 始终反映全部待办，不受筛选影响
    assert by_type["data"]["summary"]["total"] == 5

    high_only = pm.get("/api/todos", params={"severity": "high"}).json()["data"]["todos"]
    assert all(t["severity"] == "high" for t in high_only)
