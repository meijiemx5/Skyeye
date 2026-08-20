"""End-to-end API tests for the reimbursement chain and the category constraint.

链路: 提交报销 → 主管审核 → 项目收款 → 创建单据 → 财务审核 → 凭证生成 → 付款
"""
import pytest

from tests.conftest import seed_category, seed_contract, seed_project

PAYLOAD = {
    "project_id": "p1",
    "project_name": "某小区弱电",
    "amount_with_tax": 1200,
    "expense_type": "cat-material",
    "expense_category_id": "cat-material",
    "description": "买线材",
    "expense_date": "2026-08-01",
}


@pytest.fixture
def seeded(store):
    seed_category(store)
    seed_project(store)
    seed_contract(store)
    return store


def _create(client, **overrides):
    res = client.post("/api/reimbursements", json={**PAYLOAD, **overrides})
    assert res.status_code == 200, res.text
    return res.json()["data"]["reimburse_id"]


def _status(client, rid):
    return client.get(f"/api/reimbursements/{rid}").json()["data"]["status"]


# --- 完整链路 ---------------------------------------------------------------

def test_full_chain_reaches_paid(seeded, as_user):
    admin = as_user("admin")
    rid = _create(admin, )

    assert _status(admin, rid) == "pending_review"

    assert admin.post(f"/api/reimbursements/{rid}/audit",
                      json={"action": "approved"}).status_code == 200
    assert _status(admin, rid) == "manager_approved"

    assert admin.post(f"/api/reimbursements/{rid}/confirm-receipt", json={
        "contract_id": "c1", "receipt_amount": 400000, "receipt_date": "2026-08-10",
    }).status_code == 200
    assert _status(admin, rid) == "receipt_confirmed"

    doc = admin.post(f"/api/reimbursements/{rid}/create-document", json={})
    assert doc.status_code == 200
    assert _status(admin, rid) == "document_created"

    assert admin.post(f"/api/reimbursements/{rid}/audit",
                      json={"action": "approved"}).status_code == 200
    assert _status(admin, rid) == "finance_approved"

    voucher = admin.post(f"/api/reimbursements/{rid}/generate-voucher", json={})
    assert voucher.status_code == 200
    assert _status(admin, rid) == "voucher_generated"

    assert admin.post(f"/api/reimbursements/{rid}/pay", json={
        "payment_amount": 1200, "payment_method": "bank_transfer", "payment_time": "2026-08-20 10:00",
    }).status_code == 200

    detail = admin.get(f"/api/reimbursements/{rid}").json()["data"]
    assert detail["status"] == "paid"
    assert detail["next_step_label"] is None
    assert detail["document_no"].startswith("BX-")
    assert detail["voucher_no"].startswith("PZ-")
    assert detail["receipt_amount"] == 400000
    assert detail["receipt_contract_no"] == "JF-20260101-C1"
    # 每个环节都留下审批日志
    assert [log["audit_level"] for log in detail["audit_logs"]] == [
        "manager", "receipt", "document", "finance", "voucher", "payment"]


def test_receipt_is_a_hard_gate_before_document(seeded, as_user):
    """未确认项目收款不能创建单据。"""
    admin = as_user("admin")
    rid = _create(admin)
    admin.post(f"/api/reimbursements/{rid}/audit", json={"action": "approved"})

    res = admin.post(f"/api/reimbursements/{rid}/create-document", json={})
    assert res.status_code == 400
    assert "项目收款确认" in res.json()["detail"]
    assert _status(admin, rid) == "manager_approved"


def test_cannot_pay_before_voucher(seeded, as_user):
    admin = as_user("admin")
    rid = _create(admin)
    for call in (
        ("audit", {"action": "approved"}),
        ("confirm-receipt", {"contract_id": "c1", "receipt_amount": 100}),
        ("create-document", {}),
        ("audit", {"action": "approved"}),
    ):
        admin.post(f"/api/reimbursements/{rid}/{call[0]}", json=call[1])
    assert _status(admin, rid) == "finance_approved"

    res = admin.post(f"/api/reimbursements/{rid}/pay", json={
        "payment_amount": 1200, "payment_method": "cash", "payment_time": "2026-08-20 10:00"})
    assert res.status_code == 400
    assert "凭证生成" in res.json()["detail"]


def test_rejection_sends_it_back_and_edit_restarts_the_chain(seeded, as_user):
    admin = as_user("admin")
    rid = _create(admin)
    admin.post(f"/api/reimbursements/{rid}/audit", json={"action": "rejected", "comments": "发票不清"})
    assert _status(admin, rid) == "rejected"

    assert admin.put(f"/api/reimbursements/{rid}", json={"amount_with_tax": 1000}).status_code == 200
    assert _status(admin, rid) == "pending_review"


def test_approved_reimbursement_can_no_longer_be_edited(seeded, as_user):
    admin = as_user("admin")
    rid = _create(admin)
    admin.post(f"/api/reimbursements/{rid}/audit", json={"action": "approved"})

    res = admin.put(f"/api/reimbursements/{rid}", json={"amount_with_tax": 9999})
    assert res.status_code == 400
    assert "不允许修改" in res.json()["detail"]


# --- 收款门禁的角色与跳过 ---------------------------------------------------

def test_project_manager_cannot_confirm_receipt(seeded, as_user):
    admin = as_user("admin")
    rid = _create(admin)
    admin.post(f"/api/reimbursements/{rid}/audit", json={"action": "approved"})

    pm = as_user("pm")
    res = pm.post(f"/api/reimbursements/{rid}/confirm-receipt",
                  json={"contract_id": "c1", "receipt_amount": 100})
    assert res.status_code == 403


def test_finance_cannot_skip_the_receipt_gate(seeded, as_user):
    admin = as_user("admin")
    rid = _create(admin)
    admin.post(f"/api/reimbursements/{rid}/audit", json={"action": "approved"})

    finance = as_user("finance")
    res = finance.post(f"/api/reimbursements/{rid}/confirm-receipt",
                       json={"skip": True, "skip_reason": "先垫付"})
    assert res.status_code == 403
    assert "管理员" in res.json()["detail"]


def test_admin_skip_requires_a_reason_and_is_recorded(seeded, as_user):
    admin = as_user("admin")
    rid = _create(admin)
    admin.post(f"/api/reimbursements/{rid}/audit", json={"action": "approved"})

    blank = admin.post(f"/api/reimbursements/{rid}/confirm-receipt",
                       json={"skip": True, "skip_reason": "   "})
    assert blank.status_code == 400
    assert "原因" in blank.json()["detail"]

    ok = admin.post(f"/api/reimbursements/{rid}/confirm-receipt",
                    json={"skip": True, "skip_reason": "小额差旅费先行垫付"})
    assert ok.status_code == 200

    detail = admin.get(f"/api/reimbursements/{rid}").json()["data"]
    assert detail["status"] == "receipt_confirmed"
    assert detail["receipt_skipped"] is True
    assert detail["receipt_skip_reason"] == "小额差旅费先行垫付"
    assert detail["receipt_amount"] is None
    assert detail["audit_logs"][-1]["action"] == "skipped"


def test_receipt_without_contract_is_rejected(seeded, as_user):
    admin = as_user("admin")
    rid = _create(admin)
    admin.post(f"/api/reimbursements/{rid}/audit", json={"action": "approved"})

    res = admin.post(f"/api/reimbursements/{rid}/confirm-receipt", json={"receipt_amount": 100})
    assert res.status_code == 400
    assert "甲方合同" in res.json()["detail"]


# --- 审核角色路由 -----------------------------------------------------------

def test_finance_cannot_do_the_manager_audit(seeded, as_user):
    admin = as_user("admin")
    rid = _create(admin)

    res = as_user("finance").post(f"/api/reimbursements/{rid}/audit", json={"action": "approved"})
    assert res.status_code == 403
    assert "主管审核" in res.json()["detail"]


def test_project_manager_cannot_do_the_finance_audit(seeded, as_user):
    admin = as_user("admin")
    rid = _create(admin)
    for call, body in (("audit", {"action": "approved"}),
                       ("confirm-receipt", {"contract_id": "c1", "receipt_amount": 100}),
                       ("create-document", {})):
        admin.post(f"/api/reimbursements/{rid}/{call}", json=body)

    res = as_user("pm").post(f"/api/reimbursements/{rid}/audit", json={"action": "approved"})
    assert res.status_code == 403
    assert "财务审核" in res.json()["detail"]


# --- 费用大类约束: 报销环节不允许新增大类 -----------------------------------

def test_unknown_category_is_rejected(seeded, as_user):
    res = as_user("admin").post("/api/reimbursements", json={
        **PAYLOAD, "expense_category_id": "cat-invented", "expense_type": "cat-invented"})
    assert res.status_code == 400
    assert "请选择系统已有的费用大类" in res.json()["detail"]


def test_inactive_category_is_rejected(seeded, as_user):
    seed_category(seeded, category_id="cat-old", name="旧分类", is_active=False)
    res = as_user("admin").post("/api/reimbursements", json={
        **PAYLOAD, "expense_category_id": "cat-old", "expense_type": "cat-old"})
    assert res.status_code == 400
    assert "已停用" in res.json()["detail"]


def test_subcategory_must_belong_to_the_chosen_parent(seeded, as_user):
    seed_category(seeded, category_id="cat-travel", name="差旅费")
    seed_category(seeded, category_id="sub-cable", name="线материал", parent_id="cat-material", level=2)

    res = as_user("admin").post("/api/reimbursements", json={
        **PAYLOAD, "expense_category_id": "cat-travel", "expense_subcategory_id": "sub-cable"})
    assert res.status_code == 400
    assert "不属于大类" in res.json()["detail"]


def test_level_two_category_cannot_be_used_as_the_parent(seeded, as_user):
    seed_category(seeded, category_id="sub-cable", name="线材", parent_id="cat-material", level=2)
    res = as_user("admin").post("/api/reimbursements", json={
        **PAYLOAD, "expense_category_id": "sub-cable", "expense_type": "sub-cable"})
    assert res.status_code == 400
    assert "不是费用大类" in res.json()["detail"]


def test_expense_type_is_derived_server_side(seeded, as_user):
    """前端乱传 expense_type 也不会写进库 —— 服务端按分类派生。"""
    seed_category(seeded, category_id="sub-cable", name="线材", parent_id="cat-material", level=2)
    admin = as_user("admin")
    rid = _create(admin, expense_type="随便乱写的类型", expense_subcategory_id="sub-cable")

    detail = admin.get(f"/api/reimbursements/{rid}").json()["data"]
    assert detail["expense_type"] == "sub-cable"
    assert detail["expense_category_id"] == "cat-material"
    assert detail["expense_subcategory_id"] == "sub-cable"


def test_legacy_payload_with_only_expense_type_still_works(seeded, as_user):
    admin = as_user("admin")
    res = admin.post("/api/reimbursements", json={
        k: v for k, v in PAYLOAD.items() if k != "expense_category_id"})
    assert res.status_code == 200
    detail = admin.get(f"/api/reimbursements/{res.json()['data']['reimburse_id']}").json()["data"]
    assert detail["expense_category_id"] == "cat-material"


def test_category_is_revalidated_on_update(seeded, as_user):
    admin = as_user("admin")
    rid = _create(admin)
    res = admin.put(f"/api/reimbursements/{rid}", json={"expense_category_id": "cat-nope"})
    assert res.status_code == 400
