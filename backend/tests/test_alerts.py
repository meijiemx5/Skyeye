"""Tests for the project completeness checklist and todo aggregation.

HZY 2026-08-20: 项目完整组成 = 预算、报价、合同(甲方/采购)、验收资料、报销、工费(+发票)；
「验收资料迟迟不上传，那么项目就会给对应的负责人提醒，某项工作未完成」。
"""
import pytest

from app.services import alerts

TODAY = "2026-08-20"          # 项目计划完工(2026-06-30)之后
EARLY = "2026-01-05"          # 开工(2026-01-01)之后 4 天，宽限期内

PM = {"user_id": "u-pm", "role": "project_manager", "display_name": "张三"}
OTHER_PM = {"user_id": "u-pm2", "role": "project_manager", "display_name": "李四"}
ADMIN = {"user_id": "u-admin", "role": "admin", "display_name": "管理员"}
FINANCE = {"user_id": "u-fin", "role": "finance", "display_name": "财务"}
PROCUREMENT = {"user_id": "u-buy", "role": "procurement", "display_name": "采购"}
CONSTRUCTION = {"user_id": "u-work", "role": "construction", "display_name": "施工"}


def _project(**overrides):
    return {
        "project_id": "p1", "project_name": "某小区弱电", "status": "active",
        "project_manager_id": PM["user_id"], "project_manager_name": PM["display_name"],
        "start_date": "2026-01-01", "end_date": "2026-06-30",
        "budget_amount": None, "quote_amount": None,
        **overrides,
    }


def _items(checklist):
    return {item["key"]: item for item in checklist["items"]}


def _complete_project_checklist(**kwargs):
    """A project with every part in place."""
    defaults = dict(
        contracts=[
            {"contract_type": "client", "status": "signed", "amount_with_tax": 1000000},
            {"contract_type": "supplier", "status": "signed", "amount_with_tax": 300000},
            {"contract_type": "construction", "status": "signed", "amount_with_tax": 100000},
        ],
        acceptances=[{"status": "accepted", "basic_docs": [{"file_id": "f1"}]}],
        reimbursements=[],
        invoice_items=[{"amount_with_tax": 1000000, "category": "material", "tax_rate": 0.13}],
        material_cost=300000,
        used_amount=400000,
        today=TODAY,
    )
    defaults.update(kwargs)
    return alerts.evaluate_project_checklist(
        _project(budget_amount=800000, quote_amount=950000), **defaults)


# --- 空项目: 每一项都该被催 -------------------------------------------------

def test_empty_project_flags_every_required_part_as_overdue():
    checklist = alerts.evaluate_project_checklist(_project(), today=TODAY)
    items = _items(checklist)
    for key in ("budget", "quote", "client_contract", "labor_contract", "acceptance"):
        assert items[key]["status"] == alerts.OVERDUE, key
        assert items[key]["severity"] == alerts.HIGH
        assert items[key]["days_overdue"] > 0


def test_checklist_covers_all_eight_parts():
    checklist = alerts.evaluate_project_checklist(_project(), today=TODAY)
    assert tuple(_items(checklist)) == alerts.CHECKLIST_KEYS
    assert len(alerts.CHECKLIST_KEYS) == 8


def test_empty_project_health_counts_only_applicable_items():
    checklist = alerts.evaluate_project_checklist(_project(), today=TODAY)
    # 无材料成本→采购合同不适用; 无甲方合同金额→发票不适用
    assert checklist["counts"]["total"] == 6
    assert checklist["counts"]["overdue"] == 5
    assert checklist["counts"]["ok"] == 1  # 无在途报销
    assert checklist["health_score"] == pytest.approx(16.7)


def test_missing_within_grace_period_is_not_yet_overdue():
    items = _items(alerts.evaluate_project_checklist(_project(), today=EARLY))
    assert items["budget"]["status"] == alerts.MISSING
    assert items["budget"]["severity"] == alerts.MEDIUM
    assert items["budget"]["days_overdue"] == 0
    assert "2026-01-08" in items["budget"]["message"]


def test_due_dates_follow_the_grace_table():
    items = _items(alerts.evaluate_project_checklist(_project(), today=EARLY))
    assert items["budget"]["due_date"] == "2026-01-08"
    assert items["quote"]["due_date"] == "2026-01-08"
    assert items["client_contract"]["due_date"] == "2026-01-15"
    assert items["labor_contract"]["due_date"] == "2026-01-31"
    assert items["acceptance"]["due_date"] == "2026-06-30"   # 计划完工日
    assert items["invoice"]["due_date"] == "2026-07-30"      # 完工 +30 天


def test_project_without_dates_never_goes_overdue():
    checklist = alerts.evaluate_project_checklist(
        _project(start_date=None, end_date=None, created_at=None), today=TODAY)
    for item in checklist["items"]:
        assert item["status"] in (alerts.OK, alerts.MISSING)


def test_created_at_is_used_when_start_date_is_blank():
    checklist = alerts.evaluate_project_checklist(
        _project(start_date=None, created_at="2026-01-01T08:00:00+00:00"), today=TODAY)
    assert _items(checklist)["budget"]["status"] == alerts.OVERDUE


# --- 完整项目: 全绿 ---------------------------------------------------------

def test_complete_project_is_fully_healthy():
    checklist = _complete_project_checklist()
    for item in checklist["items"]:
        assert item["status"] == alerts.OK, item["key"]
    assert checklist["counts"]["total"] == 8
    assert checklist["health_score"] == 100.0


def test_draft_client_contract_does_not_count_as_signed():
    checklist = _complete_project_checklist(
        contracts=[{"contract_type": "client", "status": "draft", "amount_with_tax": 1000000}])
    item = _items(checklist)["client_contract"]
    assert item["status"] == alerts.OVERDUE
    assert "尚未签订" in item["message"]


# --- 采购合同: 只有产生材料成本才必需 ---------------------------------------

def test_supplier_contract_not_required_without_material_cost():
    item = _items(alerts.evaluate_project_checklist(
        _project(), material_cost=0, today=TODAY))["supplier_contract"]
    assert item["applicable"] is False
    assert item["status"] == alerts.OK
    assert "暂无材料采购" in item["message"]


def test_supplier_contract_required_once_material_cost_exists():
    item = _items(alerts.evaluate_project_checklist(
        _project(), material_cost=5000, today=TODAY))["supplier_contract"]
    assert item["applicable"] is True
    assert item["status"] == alerts.OVERDUE
    assert item["owner_role"] == "procurement"
    assert "5,000" in item["message"]


# --- 验收资料 ---------------------------------------------------------------

def test_acceptance_record_without_documents_still_counts_as_missing():
    """有验收记录但没上传资料, 照样要催 —— 这正是 HZY 说的场景。"""
    item = _items(alerts.evaluate_project_checklist(
        _project(), acceptances=[{"status": "pending_upload"}], today=TODAY))["acceptance"]
    assert item["status"] == alerts.OVERDUE
    assert item["owner_id"] == PM["user_id"]


def test_documents_in_any_category_satisfy_the_acceptance_rule():
    item = _items(alerts.evaluate_project_checklist(
        _project(), acceptances=[{"status": "uploaded", "compliance_docs": [{"file_id": "f"}]}],
        today=TODAY))["acceptance"]
    assert item["status"] == alerts.OK


def test_rectification_raises_the_acceptance_alert():
    item = _items(_complete_project_checklist(
        acceptances=[{"status": "needs_rectification", "basic_docs": [{"file_id": "f"}]}],
    ))["acceptance"]
    assert item["severity"] == alerts.HIGH
    assert "整改" in item["message"]


# --- 预算 -------------------------------------------------------------------

def test_over_budget_turns_the_budget_item_into_a_high_warning():
    item = _items(_complete_project_checklist(used_amount=900000))["budget"]
    assert item["status"] == alerts.WARNING
    assert item["severity"] == alerts.HIGH
    assert "超预算" in item["message"]


def test_near_budget_is_a_medium_warning():
    item = _items(_complete_project_checklist(used_amount=732000))["budget"]
    assert item["status"] == alerts.WARNING
    assert item["severity"] == alerts.MEDIUM
    assert "91.5%" in item["message"]


# --- 发票 -------------------------------------------------------------------

def test_partially_invoiced_contract_is_flagged_with_the_remaining_amount():
    """40 万预付款开完, 剩 60 万未开。"""
    item = _items(_complete_project_checklist(
        invoice_items=[{"amount_with_tax": 400000}]))["invoice"]
    assert item["status"] == alerts.OVERDUE
    assert item["owner_role"] == "finance"
    assert "600,000" in item["message"]


def test_fully_invoiced_contract_is_ok():
    assert _items(_complete_project_checklist())["invoice"]["status"] == alerts.OK


def test_invoice_not_applicable_without_client_contract_amount():
    item = _items(alerts.evaluate_project_checklist(_project(), today=TODAY))["invoice"]
    assert item["applicable"] is False


# --- 报销停留 ---------------------------------------------------------------

def test_reimbursement_stuck_beyond_the_limit_is_overdue():
    checklist = _complete_project_checklist(reimbursements=[
        {"reimburse_id": "r1", "status": "document_created", "updated_at": "2026-08-01"},
    ])
    item = _items(checklist)["reimbursement"]
    assert item["status"] == alerts.OVERDUE
    assert item["days_overdue"] == 19
    assert "停留超过" in item["message"]


def test_recent_reimbursement_does_not_trigger_an_alert():
    item = _items(_complete_project_checklist(reimbursements=[
        {"reimburse_id": "r1", "status": "pending_review", "updated_at": "2026-08-19"},
    ]))["reimbursement"]
    assert item["status"] == alerts.OK
    assert "1 笔" in item["message"]


@pytest.mark.parametrize("status", ["paid", "rejected"])
def test_settled_reimbursements_are_never_stale(status):
    item = _items(_complete_project_checklist(reimbursements=[
        {"reimburse_id": "r1", "status": status, "updated_at": "2025-01-01"},
    ]))["reimbursement"]
    assert item["status"] == alerts.OK


# --- 待办归属 ---------------------------------------------------------------

def _empty_checklists():
    return [alerts.evaluate_project_checklist(_project(), today=TODAY)]


def test_project_manager_sees_only_their_own_project_items():
    todos = alerts.todos_from_checklists(_empty_checklists(), PM)
    keys = {t["todo_id"].split(":")[-1] for t in todos}
    assert keys == {"budget", "quote", "client_contract", "labor_contract", "acceptance"}
    assert all(t["link"] == "/projects/p1" for t in todos)


def test_another_project_manager_sees_nothing():
    assert alerts.todos_from_checklists(_empty_checklists(), OTHER_PM) == []


def test_admin_sees_every_unfinished_item():
    todos = alerts.todos_from_checklists(_empty_checklists(), ADMIN)
    assert len(todos) == 5


def test_finance_only_gets_the_finance_owned_items():
    checklists = [_complete_project_checklist(invoice_items=[{"amount_with_tax": 400000}])]
    todos = alerts.todos_from_checklists(checklists, FINANCE)
    assert [t["todo_id"].split(":")[-1] for t in todos] == ["invoice"]


def test_procurement_gets_the_supplier_contract_item():
    checklists = [alerts.evaluate_project_checklist(_project(), material_cost=5000, today=TODAY)]
    todos = alerts.todos_from_checklists(checklists, PROCUREMENT)
    assert [t["todo_id"].split(":")[-1] for t in todos] == ["supplier_contract"]


def test_completed_items_never_become_todos():
    assert alerts.todos_from_checklists([_complete_project_checklist()], ADMIN) == []


def test_todo_carries_project_context_and_due_date():
    todo = next(t for t in alerts.todos_from_checklists(_empty_checklists(), PM)
                if t["todo_id"].endswith("acceptance"))
    assert todo["project_id"] == "p1"
    assert todo["project_name"] == "某小区弱电"
    assert todo["due_date"] == "2026-06-30"
    assert todo["days_pending"] > 0
    assert "验收资料未完成" in todo["title"]


# --- 报销待办按链路环节派给对应角色 -----------------------------------------

def _reimburse(status, **overrides):
    return {
        "reimburse_id": "r1", "status": status, "applicant_id": "u-work",
        "applicant_name": "施工", "amount_with_tax": 1200, "description": "买线材",
        "project_id": "p1", "project_name": "某小区弱电", "updated_at": TODAY,
        **overrides,
    }


@pytest.mark.parametrize("status,user,expected_title", [
    ("pending_review", PM, "待主管审核"),
    ("manager_approved", FINANCE, "待确认项目收款"),
    ("receipt_confirmed", FINANCE, "待创建单据"),
    ("document_created", FINANCE, "待财务审核"),
    ("finance_approved", FINANCE, "待生成凭证"),
    ("voucher_generated", FINANCE, "待付款"),
])
def test_each_chain_step_lands_on_the_right_desk(status, user, expected_title):
    todos = alerts.todos_from_reimbursements([_reimburse(status)], user, today=TODAY)
    assert len(todos) == 1
    assert expected_title in todos[0]["title"]


@pytest.mark.parametrize("status", ["manager_approved", "document_created", "voucher_generated"])
def test_project_manager_is_not_asked_to_do_finance_steps(status):
    assert alerts.todos_from_reimbursements([_reimburse(status)], PM, today=TODAY) == []


def test_paid_reimbursement_produces_no_todo():
    assert alerts.todos_from_reimbursements([_reimburse("paid")], FINANCE, today=TODAY) == []


def test_rejected_reimbursement_goes_back_to_the_applicant_only():
    rejected = _reimburse("rejected")
    assert alerts.todos_from_reimbursements([rejected], FINANCE, today=TODAY) == []
    applicant = {"user_id": "u-work", "role": "construction"}
    todos = alerts.todos_from_reimbursements([rejected], applicant, today=TODAY)
    assert len(todos) == 1
    assert "驳回" in todos[0]["title"]


def test_long_pending_reimbursement_escalates_to_high():
    fresh = alerts.todos_from_reimbursements(
        [_reimburse("document_created", updated_at="2026-08-19")], FINANCE, today=TODAY)[0]
    stale = alerts.todos_from_reimbursements(
        [_reimburse("document_created", updated_at="2026-08-01")], FINANCE, today=TODAY)[0]
    assert fresh["severity"] == alerts.MEDIUM
    assert stale["severity"] == alerts.HIGH
    assert stale["days_pending"] == 19
    assert "已停留 19 天" in stale["detail"]


# --- 验收整改 / 库存待办 ----------------------------------------------------

def test_rectification_todo_for_project_manager():
    acceptances = [{
        "acceptance_id": "a1", "project_id": "p1", "project_name": "某小区弱电",
        "status": "needs_rectification", "rectification_requirements": "补签字页",
        "rectification_deadline": "2026-09-01",
    }]
    todos = alerts.todos_from_acceptances(acceptances, PM)
    assert len(todos) == 1
    assert todos[0]["severity"] == alerts.HIGH
    assert todos[0]["due_date"] == "2026-09-01"
    assert alerts.todos_from_acceptances(acceptances, FINANCE) == []


def test_accepted_records_produce_no_rectification_todo():
    assert alerts.todos_from_acceptances(
        [{"acceptance_id": "a1", "status": "accepted"}], ADMIN) == []


def test_stock_todos_go_to_procurement_and_warehouse():
    materials = [
        {"material_id": "m1", "material_name": "网线", "unit": "米",
         "stock_quantity": 0, "stock_status": "out_of_stock", "min_stock_threshold": 100},
        {"material_id": "m2", "material_name": "水晶头", "unit": "个",
         "stock_quantity": 20, "stock_status": "warning", "min_stock_threshold": 50},
        {"material_id": "m3", "material_name": "交换机", "unit": "台",
         "stock_quantity": 5, "stock_status": "normal"},
    ]
    todos = alerts.todos_from_stock(materials, PROCUREMENT)
    assert len(todos) == 2
    assert todos[0]["severity"] == alerts.HIGH   # 缺货
    assert todos[1]["severity"] == alerts.MEDIUM
    assert alerts.todos_from_stock(materials, CONSTRUCTION) == []


# --- 排序与汇总 -------------------------------------------------------------

def test_sort_puts_high_severity_and_longest_waiting_first():
    todos = [
        {"severity": alerts.MEDIUM, "days_pending": 30, "title": "b", "type": "x"},
        {"severity": alerts.HIGH, "days_pending": 1, "title": "a", "type": "x"},
        {"severity": alerts.HIGH, "days_pending": 10, "title": "c", "type": "x"},
    ]
    assert [t["title"] for t in alerts.sort_todos(todos)] == ["c", "a", "b"]


def test_summary_counts_by_severity_and_type():
    todos = [
        {"severity": alerts.HIGH, "type": "project_checklist", "days_pending": 1, "title": "a"},
        {"severity": alerts.HIGH, "type": "reimbursement", "days_pending": 1, "title": "b"},
        {"severity": alerts.MEDIUM, "type": "reimbursement", "days_pending": 1, "title": "c"},
    ]
    summary = alerts.summarize_todos(todos)
    assert summary["total"] == 3
    assert summary["high"] == 2
    assert summary["medium"] == 1
    assert summary["by_type"] == {"project_checklist": 1, "reimbursement": 2}


def test_summary_of_no_todos_is_all_zero():
    assert alerts.summarize_todos([]) == {
        "total": 0, "high": 0, "medium": 0, "low": 0, "by_type": {}}
