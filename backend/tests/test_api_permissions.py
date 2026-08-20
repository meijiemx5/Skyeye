"""API-level checks for the tightened view permissions.

HZY 2026-08-20: 项目列表 / 合同 / 验收资料 仅管理员、项目负责人可查看。
财务与采购仍要能干活，所以精简 options 接口必须对他们开放。
"""
import pytest

from tests.conftest import seed_category, seed_contract, seed_project

RESTRICTED_ROLES = ["finance", "procurement", "construction", "warehouse"]


@pytest.fixture
def seeded(store):
    seed_project(store, project_id="p1", name="某小区弱电", manager_id="u-pm")
    seed_project(store, project_id="p2", name="别人的项目", manager_id="u-other")
    seed_contract(store, contract_id="c1", project_id="p1", contract_type="client")
    seed_contract(store, contract_id="c2", project_id="p2", contract_type="supplier")
    return store


# --- 项目列表 ---------------------------------------------------------------

@pytest.mark.parametrize("role", RESTRICTED_ROLES)
def test_project_list_is_closed_to_other_roles(seeded, as_user, role):
    assert as_user(role).get("/api/projects").status_code == 403


@pytest.mark.parametrize("role", ["admin", "pm"])
def test_project_list_open_to_admin_and_pm(seeded, as_user, role):
    assert as_user(role).get("/api/projects").status_code == 200


def test_project_manager_sees_only_their_own_projects(seeded, as_user):
    data = as_user("pm").get("/api/projects").json()["data"]
    assert [p["project_id"] for p in data] == ["p1"]


def test_project_manager_cannot_open_someone_elses_project(seeded, as_user):
    pm = as_user("pm")
    assert pm.get("/api/projects/p1").status_code == 200
    res = pm.get("/api/projects/p2")
    assert res.status_code == 403
    assert "自己负责" in res.json()["detail"]


@pytest.mark.parametrize("role", RESTRICTED_ROLES + ["admin", "pm"])
def test_project_options_stay_open_to_everyone(seeded, as_user, role):
    res = as_user(role).get("/api/projects/options")
    assert res.status_code == 200
    data = res.json()["data"]
    assert {p["project_id"] for p in data} == {"p1", "p2"}
    # 精简选项不泄露金额等字段
    assert set(data[0]) == {"project_id", "project_name", "status"}


# --- 合同 -------------------------------------------------------------------

@pytest.mark.parametrize("role", RESTRICTED_ROLES)
def test_contract_view_is_closed_to_other_roles(seeded, as_user, role):
    client = as_user(role)
    assert client.get("/api/contracts").status_code == 403
    assert client.get("/api/contracts/c1").status_code == 403
    assert client.get("/api/contracts/statistics").status_code == 403


@pytest.mark.parametrize("role", ["finance", "procurement"])
def test_contract_options_open_to_finance_and_procurement(seeded, as_user, role):
    res = as_user(role).get("/api/contracts/options")
    assert res.status_code == 200
    data = res.json()["data"]
    assert {c["contract_id"] for c in data} == {"c1", "c2"}
    # 只有付款需要的字段，没有条款/附件/发票
    assert set(data[0]) == {
        "contract_id", "contract_no", "contract_name", "contract_type",
        "project_id", "project_name", "amount_with_tax", "paid_amount", "status"}


@pytest.mark.parametrize("role", ["construction", "warehouse"])
def test_contract_options_still_closed_to_field_roles(seeded, as_user, role):
    assert as_user(role).get("/api/contracts/options").status_code == 403


def test_contract_options_can_filter_by_type_for_receipt_confirmation(seeded, as_user):
    res = as_user("finance").get("/api/contracts/options", params={"contract_type": "client"})
    assert [c["contract_id"] for c in res.json()["data"]] == ["c1"]


def test_project_manager_contracts_are_scoped_to_their_projects(seeded, as_user):
    pm = as_user("pm")
    assert [c["contract_id"] for c in pm.get("/api/contracts").json()["data"]] == ["c1"]
    assert pm.get("/api/contracts/c2").status_code == 403
    assert pm.get("/api/contracts/statistics").json()["data"]["total_count"] == 1


def test_finance_keeps_contract_payment_despite_losing_view(seeded, as_user):
    """收紧后财务仍能登记合同付款 —— 否则等于把财务的活废掉了。"""
    finance = as_user("finance")
    assert finance.get("/api/contracts").status_code == 403
    res = finance.post("/api/contracts/c1/payment", json={
        "amount": 50000, "payment_method": "bank_transfer", "payment_date": "2026-08-20"})
    assert res.status_code == 200
    assert res.json()["data"]["paid_amount"] == 50000


# --- 验收资料 ---------------------------------------------------------------

@pytest.mark.parametrize("role", RESTRICTED_ROLES)
def test_acceptance_view_is_closed_to_other_roles(seeded, as_user, role):
    assert as_user(role).get("/api/acceptances").status_code == 403


@pytest.mark.parametrize("role", ["admin", "pm"])
def test_acceptance_view_open_to_admin_and_pm(seeded, as_user, role):
    assert as_user(role).get("/api/acceptances").status_code == 200


# --- 报销对所有人开放（提交报销是全员功能）---------------------------------

@pytest.mark.parametrize("role", RESTRICTED_ROLES + ["admin", "pm"])
def test_reimbursement_list_stays_open(seeded, as_user, role):
    assert as_user(role).get("/api/reimbursements").status_code == 200


def _submit(client, project_id):
    return client.post("/api/reimbursements", json={
        "project_id": project_id, "project_name": "x", "amount_with_tax": 100,
        "expense_type": "cat-material", "expense_category_id": "cat-material",
        "description": "买线材", "expense_date": "2026-08-01"}).json()["data"]["reimburse_id"]


def test_project_manager_sees_reimbursements_they_must_audit(seeded, as_user):
    """主管审核的那些报销必须出现在他的列表里，否则待办点进去是空的。"""
    seed_category(seeded)
    worker = as_user("construction")            # 施工人员提交，项目负责人是别人
    mine = _submit(worker, "p1")                # p1 由 u-pm 负责
    theirs = _submit(worker, "p2")              # p2 是别人的项目

    visible = {r["reimburse_id"] for r in as_user("pm").get("/api/reimbursements").json()["data"]}
    assert mine in visible
    assert theirs not in visible


def test_applicant_always_sees_their_own_submission(seeded, as_user):
    seed_category(seeded)
    worker = as_user("construction")
    rid = _submit(worker, "p2")
    visible = {r["reimburse_id"] for r in worker.get("/api/reimbursements").json()["data"]}
    assert visible == {rid}
