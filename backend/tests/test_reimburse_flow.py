"""Tests for the reimbursement workflow state machine.

链路 (HZY 2026-08-20): 提交报销 → 项目收款 → 创建单据 → 财务审核 → 凭证生成 → 付款
"""
import re

import pytest

from app.services import reimburse_flow as flow

FULL_CHAIN = [
    (flow.PENDING_REVIEW, flow.AUDIT_MANAGER, flow.MANAGER_APPROVED),
    (flow.MANAGER_APPROVED, flow.CONFIRM_RECEIPT, flow.RECEIPT_CONFIRMED),
    (flow.RECEIPT_CONFIRMED, flow.CREATE_DOCUMENT, flow.DOCUMENT_CREATED),
    (flow.DOCUMENT_CREATED, flow.AUDIT_FINANCE, flow.FINANCE_APPROVED),
    (flow.FINANCE_APPROVED, flow.GENERATE_VOUCHER, flow.VOUCHER_GENERATED),
    (flow.VOUCHER_GENERATED, flow.PAY, flow.PAID),
]


# --- 顺序执行整条链路 -------------------------------------------------------

def test_full_chain_walks_from_submission_to_payment():
    status = flow.PENDING_REVIEW
    for expected_from, step, expected_to in FULL_CHAIN:
        assert status == expected_from
        status = flow.apply_step(step, status)
        assert status == expected_to
    assert status == flow.PAID


@pytest.mark.parametrize("from_status,step,to_status", FULL_CHAIN)
def test_each_step_advances_exactly_one_status(from_status, step, to_status):
    assert flow.apply_step(step, from_status) == to_status


def test_status_order_matches_the_required_chain():
    assert flow.STATUS_ORDER == (
        flow.PENDING_REVIEW, flow.MANAGER_APPROVED, flow.RECEIPT_CONFIRMED,
        flow.DOCUMENT_CREATED, flow.FINANCE_APPROVED, flow.VOUCHER_GENERATED, flow.PAID,
    )


@pytest.mark.parametrize("from_status,step,_to", FULL_CHAIN)
def test_next_step_points_at_the_pending_action(from_status, step, _to):
    assert flow.next_step(from_status) == step
    assert flow.next_step_label(from_status) == flow.STEPS[step]["label"]


def test_paid_and_rejected_have_no_next_step():
    assert flow.next_step(flow.PAID) is None
    assert flow.next_step(flow.REJECTED) is None


# --- 硬门禁: 不许跳步 -------------------------------------------------------

def test_cannot_create_document_before_receipt_is_confirmed():
    """项目收款是硬门禁 —— 主管审完不能直接开单据。"""
    with pytest.raises(flow.TransitionError) as exc:
        flow.apply_step(flow.CREATE_DOCUMENT, flow.MANAGER_APPROVED)
    assert "项目收款确认" in str(exc.value)


def test_cannot_finance_audit_before_document_exists():
    with pytest.raises(flow.TransitionError):
        flow.apply_step(flow.AUDIT_FINANCE, flow.MANAGER_APPROVED)
    with pytest.raises(flow.TransitionError):
        flow.apply_step(flow.AUDIT_FINANCE, flow.RECEIPT_CONFIRMED)


def test_cannot_pay_before_voucher_is_generated():
    with pytest.raises(flow.TransitionError) as exc:
        flow.apply_step(flow.PAY, flow.FINANCE_APPROVED)
    assert "凭证生成" in str(exc.value)


def test_cannot_pay_straight_after_submission():
    with pytest.raises(flow.TransitionError):
        flow.apply_step(flow.PAY, flow.PENDING_REVIEW)


def test_paid_reimbursement_is_closed_for_further_steps():
    for step in flow.STEPS:
        with pytest.raises(flow.TransitionError) as exc:
            flow.apply_step(step, flow.PAID)
        assert "已付款" in str(exc.value)


def test_rejected_reimbursement_needs_resubmission():
    for step in flow.STEPS:
        with pytest.raises(flow.TransitionError) as exc:
            flow.apply_step(step, flow.REJECTED)
        assert "驳回" in str(exc.value)


def test_unknown_step_is_rejected():
    with pytest.raises(flow.TransitionError):
        flow.apply_step("teleport", flow.PENDING_REVIEW)


# --- 驳回 -------------------------------------------------------------------

@pytest.mark.parametrize("status,step", [
    (flow.PENDING_REVIEW, flow.AUDIT_MANAGER),
    (flow.DOCUMENT_CREATED, flow.AUDIT_FINANCE),
])
def test_review_steps_can_reject(status, step):
    assert flow.apply_step(step, status, "rejected") == flow.REJECTED


@pytest.mark.parametrize("status,step", [
    (flow.MANAGER_APPROVED, flow.CONFIRM_RECEIPT),
    (flow.RECEIPT_CONFIRMED, flow.CREATE_DOCUMENT),
    (flow.FINANCE_APPROVED, flow.GENERATE_VOUCHER),
    (flow.VOUCHER_GENERATED, flow.PAY),
])
def test_non_review_steps_cannot_reject(status, step):
    with pytest.raises(flow.TransitionError) as exc:
        flow.apply_step(step, status, "rejected")
    assert "不支持驳回" in str(exc.value)


# --- 审核级别路由 -----------------------------------------------------------

def test_audit_step_is_derived_from_status():
    assert flow.audit_step_for_status(flow.PENDING_REVIEW) == flow.AUDIT_MANAGER
    assert flow.audit_step_for_status(flow.DOCUMENT_CREATED) == flow.AUDIT_FINANCE


@pytest.mark.parametrize("status", [
    flow.MANAGER_APPROVED, flow.RECEIPT_CONFIRMED, flow.FINANCE_APPROVED,
    flow.VOUCHER_GENERATED, flow.PAID, flow.REJECTED,
])
def test_audit_is_refused_where_no_review_is_pending(status):
    with pytest.raises(flow.TransitionError):
        flow.audit_step_for_status(status)


def test_audit_steps_map_to_distinct_permissions():
    assert flow.STEPS[flow.AUDIT_MANAGER]["permission"] == "reimburse:audit_manager"
    assert flow.STEPS[flow.AUDIT_FINANCE]["permission"] == "reimburse:audit_finance"


# --- 老数据兼容: 历史状态都还在链路上, 不会卡死 -----------------------------

@pytest.mark.parametrize("legacy_status", [flow.MANAGER_APPROVED, flow.FINANCE_APPROVED])
def test_legacy_statuses_can_still_reach_paid(legacy_status):
    status = legacy_status
    guard = 0
    while status != flow.PAID and guard < 10:
        step = flow.next_step(status)
        assert step is not None, f"{status} 卡死了"
        status = flow.apply_step(step, status)
        guard += 1
    assert status == flow.PAID


# --- 编辑权限与进度 ---------------------------------------------------------

def test_only_pending_and_rejected_are_editable():
    assert flow.is_editable(flow.PENDING_REVIEW) is True
    assert flow.is_editable(flow.REJECTED) is True
    for status in (flow.MANAGER_APPROVED, flow.RECEIPT_CONFIRMED, flow.DOCUMENT_CREATED,
                   flow.FINANCE_APPROVED, flow.VOUCHER_GENERATED, flow.PAID):
        assert flow.is_editable(status) is False


def test_progress_index_tracks_the_chain():
    assert flow.progress_index(flow.PENDING_REVIEW) == 0
    assert flow.progress_index(flow.PAID) == len(flow.STATUS_ORDER) - 1
    assert flow.progress_index(flow.REJECTED) == -1


def test_in_flight_excludes_paid():
    assert flow.PAID not in flow.IN_FLIGHT_STATUSES
    assert flow.DOCUMENT_CREATED in flow.IN_FLIGHT_STATUSES


def test_every_status_has_a_chinese_label():
    for status in flow.STATUS_ORDER + (flow.REJECTED,):
        assert flow.status_label(status) != status


# --- 单据号 / 凭证号 --------------------------------------------------------

def test_document_and_voucher_numbers_use_distinct_prefixes():
    assert re.fullmatch(r"BX-\d{8}-[0-9A-F]{4}", flow.generate_document_no())
    assert re.fullmatch(r"PZ-\d{8}-[0-9A-F]{4}", flow.generate_voucher_no())


def test_serial_numbers_accept_a_fixed_date_and_stay_unique():
    numbers = {flow.generate_document_no("20260820") for _ in range(20)}
    assert all(n.startswith("BX-20260820-") for n in numbers)
    assert len(numbers) > 1
