"""Reimbursement router - 完整链路: 提交报销 → 项目收款 → 创建单据 → 财务审核 → 凭证生成 → 付款.

状态流转规则集中在 services/reimburse_flow.py，本文件只负责取数、落库、留痕。
费用大类只能选系统已有的启用分类，报销环节不允许新增大类档案。
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
from pynamodb.exceptions import DoesNotExist
from typing import Optional

from ..models.reimbursement import ReimbursementModel, AuditLogMap
from ..models.reimburse_category import ReimburseCategoryModel
from ..models.contract import ContractModel
from ..schemas.reimbursement import (
    ReimbursementCreate, ReimbursementUpdate, ReimbursementAudit, ReimbursementPayment,
    ReimbursementReceipt, ReimbursementDocument, ReimbursementVoucher,
)
from ..schemas.common import APIResponse
from ..utils.auth import get_current_user
from ..utils.attachments import to_attachment_maps, attachment_dicts
from ..utils.permissions import require_permission, has_permission
from ..utils.scoping import own_project_ids
from ..services.audit import log_action
from ..services import reimburse_flow as flow

router = APIRouter(prefix="/api/reimbursements", tags=["报销管理"])


def _user_name(u: dict) -> str:
    return f"{u.get('username','')}({u.get('display_name','')})"


def _reimburse_to_dict(r):
    return {
        "reimburse_id": r.reimburse_id,
        "applicant_id": r.applicant_id,
        "applicant_name": r.applicant_name,
        "project_id": r.project_id,
        "project_name": r.project_name,
        "amount_with_tax": r.amount_with_tax,
        "amount_without_tax": r.amount_without_tax,
        "expense_type": r.expense_type,
        "expense_category_id": r.expense_category_id,
        "expense_subcategory_id": r.expense_subcategory_id,
        "description": r.description,
        "expense_date": r.expense_date,
        "status": r.status,
        "status_label": flow.status_label(r.status),
        "next_step": flow.next_step(r.status),
        "next_step_label": flow.next_step_label(r.status),
        "audit_logs": [
            {"auditor_id": a.auditor_id, "auditor_name": a.auditor_name,
             "audit_time": a.audit_time, "action": a.action,
             "comments": a.comments, "audit_level": a.audit_level}
            for a in (r.audit_logs or [])
        ],
        "current_reviewer_id": r.current_reviewer_id,
        "current_reviewer_name": r.current_reviewer_name,
        "payment_amount": r.payment_amount,
        "payment_method": r.payment_method,
        "payment_time": r.payment_time,
        "payment_status": r.payment_status,
        "payment_failure_reason": r.payment_failure_reason,
        "vouchers": attachment_dicts(r.vouchers),
        "payment_receipt": attachment_dicts(r.payment_receipt),
        # 链路留痕
        "receipt_contract_id": r.receipt_contract_id,
        "receipt_contract_no": r.receipt_contract_no,
        "receipt_amount": r.receipt_amount,
        "receipt_date": r.receipt_date,
        "receipt_note": r.receipt_note,
        "receipt_confirmed_at": r.receipt_confirmed_at,
        "receipt_confirmed_by_name": r.receipt_confirmed_by_name,
        "receipt_skipped": r.receipt_skipped,
        "receipt_skip_reason": r.receipt_skip_reason,
        "document_no": r.document_no,
        "document_created_at": r.document_created_at,
        "document_created_by_name": r.document_created_by_name,
        "voucher_no": r.voucher_no,
        "voucher_generated_at": r.voucher_generated_at,
        "voucher_generated_by_name": r.voucher_generated_by_name,
        "voucher_files": attachment_dicts(r.voucher_files),
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _get_or_404(reimburse_id: str) -> ReimbursementModel:
    try:
        return ReimbursementModel.get(
            ReimbursementModel.make_pk(reimburse_id), ReimbursementModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="报销记录不存在")


def _client_contract(contract_id: str, project_id: str | None) -> ContractModel:
    """Load the 甲方合同 backing a receipt confirmation, validating the reference."""
    try:
        contract = ContractModel.get(
            ContractModel.make_pk(contract_id), ContractModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=400, detail="所选甲方合同不存在")
    if contract.contract_type != "client":
        raise HTTPException(status_code=400, detail="项目收款只能关联甲方合同")
    if project_id and contract.project_id and contract.project_id != project_id:
        raise HTTPException(
            status_code=400, detail="所选甲方合同不属于该报销关联的项目")
    return contract


def _append_audit_log(r, current_user: dict, action: str, comments: str | None, audit_level: str, now: str):
    log = AuditLogMap()
    log.auditor_id = current_user["user_id"]
    log.auditor_name = current_user["display_name"]
    log.audit_time = now
    log.action = action
    log.comments = comments
    log.audit_level = audit_level
    r.audit_logs = list(r.audit_logs or []) + [log]


def _advance(r, step: str, current_user: dict, *, action: str = "approved",
             comments: str | None = None) -> str:
    """Validate + apply one workflow step, appending the audit log entry."""
    try:
        new_status = flow.apply_step(step, r.status, action)
    except flow.TransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    now = datetime.now(timezone.utc).isoformat()
    _append_audit_log(r, current_user, action, comments, flow.STEPS[step]["audit_level"], now)
    r.status = new_status
    r.GSI1PK = ReimbursementModel.make_gsi1pk(new_status)
    r.updated_at = now
    return now


# --- 费用大类校验 -----------------------------------------------------------
# HZY 2026-08-20: 报销环节不允许新增费用大类，只能选择系统已有的费用大类。
# 服务端派生 expense_type 并忽略前端传值，避免绕过校验写入野值。

def _active_category(category_id: str, label: str) -> ReimburseCategoryModel:
    try:
        category = ReimburseCategoryModel.get(
            ReimburseCategoryModel.make_pk(category_id), ReimburseCategoryModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=400, detail=f"{label}不存在，请选择系统已有的费用大类")
    if not category.is_active:
        raise HTTPException(status_code=400, detail=f"{label}「{category.name}」已停用，请选择其他分类")
    return category


def _resolve_expense_category(category_id: Optional[str], subcategory_id: Optional[str],
                              legacy_expense_type: Optional[str]) -> dict:
    """Validate the expense category selection; derive the stored expense_type."""
    if not category_id:
        # 老客户端只传 expense_type：也必须是分类表里已存在且启用的分类
        if not legacy_expense_type:
            raise HTTPException(status_code=400, detail="请选择报销费用大类")
        category = _active_category(legacy_expense_type, "费用分类")
        parent_id = category.parent_id or category.category_id
        return {
            "expense_type": category.category_id,
            "expense_category_id": parent_id,
            "expense_subcategory_id": category.category_id if category.parent_id else None,
        }

    parent = _active_category(category_id, "费用大类")
    if int(parent.level or 1) != 1:
        raise HTTPException(status_code=400, detail=f"「{parent.name}」不是费用大类，请选择一级分类")

    if not subcategory_id:
        return {
            "expense_type": parent.category_id,
            "expense_category_id": parent.category_id,
            "expense_subcategory_id": None,
        }

    child = _active_category(subcategory_id, "费用子类")
    if child.parent_id != parent.category_id:
        raise HTTPException(
            status_code=400, detail=f"子类「{child.name}」不属于大类「{parent.name}」")
    return {
        "expense_type": child.category_id,
        "expense_category_id": parent.category_id,
        "expense_subcategory_id": child.category_id,
    }


# --- CRUD -------------------------------------------------------------------

@router.get("")
def list_reimbursements(
    status: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    expense_type: Optional[str] = Query(None),
    applicant_id: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """List reimbursements."""
    results = list(ReimbursementModel.scan(filter_condition=ReimbursementModel.entity_type == "reimbursement"))

    if status:
        results = [r for r in results if r.status == status]
    if project_id:
        results = [r for r in results if r.project_id == project_id]
    if expense_type:
        results = [r for r in results if r.expense_type == expense_type or r.expense_category_id == expense_type or r.expense_subcategory_id == expense_type]
    if applicant_id:
        results = [r for r in results if r.applicant_id == applicant_id]
    if keyword:
        kw = keyword.lower()
        results = [r for r in results if
                   kw in (r.description or "").lower()
                   or kw in (r.project_name or "").lower()
                   or kw in (r.applicant_name or "").lower()]

    # Role-based filtering
    role = current_user["role"]
    uid = current_user["user_id"]
    if role == "construction":
        results = [r for r in results if r.applicant_id == uid]
    elif role == "project_manager":
        # 自己提交的 + 自己负责项目的（后者是他要做主管审核的那些）
        own = own_project_ids(uid)
        results = [r for r in results if r.applicant_id == uid or r.project_id in own]
    # finance and admin can see all

    data = [_reimburse_to_dict(r) for r in results]
    return APIResponse(data=data, total=len(data))


@router.get("/{reimburse_id}")
def get_reimbursement(reimburse_id: str, current_user: dict = Depends(get_current_user)):
    """Get reimbursement detail."""
    return APIResponse(data=_reimburse_to_dict(_get_or_404(reimburse_id)))


@router.post("")
def create_reimbursement(req: ReimbursementCreate, current_user: dict = Depends(get_current_user)):
    """Submit reimbursement application."""
    category = _resolve_expense_category(
        req.expense_category_id, req.expense_subcategory_id, req.expense_type)

    reimburse_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()

    r = ReimbursementModel()
    r.PK = ReimbursementModel.make_pk(reimburse_id)
    r.SK = ReimbursementModel.make_sk()
    r.GSI1PK = ReimbursementModel.make_gsi1pk(flow.PENDING_REVIEW)
    r.GSI1SK = f"{now}#{reimburse_id}"
    if req.project_id:
        r.GSI2PK = ReimbursementModel.make_gsi2pk(req.project_id)
        r.GSI2SK = f"REIMBURSE#{reimburse_id}"
    r.entity_type = "reimbursement"
    r.reimburse_id = reimburse_id
    r.applicant_id = current_user["user_id"]
    r.applicant_name = current_user["display_name"]
    r.project_id = req.project_id
    r.project_name = req.project_name
    r.amount_with_tax = req.amount_with_tax
    r.amount_without_tax = req.amount_without_tax
    r.expense_type = category["expense_type"]
    r.expense_category_id = category["expense_category_id"]
    r.expense_subcategory_id = category["expense_subcategory_id"]
    r.description = req.description
    r.expense_date = req.expense_date
    r.vouchers = to_attachment_maps(req.vouchers)
    r.status = flow.PENDING_REVIEW
    r.created_at = now
    r.updated_at = now
    r.created_by = current_user["user_id"]
    r.save()
    log_action(current_user["user_id"], _user_name(current_user), "create", "reimbursement", reimburse_id, f"提交报销: ¥{req.amount_with_tax} - {req.description[:30]}")
    return APIResponse(message="报销申请提交成功", data={"reimburse_id": reimburse_id})


@router.put("/{reimburse_id}")
def update_reimbursement(reimburse_id: str, req: ReimbursementUpdate, current_user: dict = Depends(get_current_user)):
    """Update reimbursement (only if rejected/pending)."""
    r = _get_or_404(reimburse_id)

    if not flow.is_editable(r.status):
        raise HTTPException(
            status_code=400,
            detail=f"当前状态为「{flow.status_label(r.status)}」，不允许修改")
    if r.applicant_id != current_user["user_id"] and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="只能修改自己的报销申请")

    # 分类变更同样要过校验（只允许已有大类）
    if req.expense_category_id or req.expense_subcategory_id or req.expense_type:
        category = _resolve_expense_category(
            req.expense_category_id or r.expense_category_id,
            req.expense_subcategory_id,
            req.expense_type or r.expense_type)
        r.expense_type = category["expense_type"]
        r.expense_category_id = category["expense_category_id"]
        r.expense_subcategory_id = category["expense_subcategory_id"]

    update_data = req.model_dump(
        exclude_none=True,
        exclude={"vouchers", "expense_type", "expense_category_id", "expense_subcategory_id"})
    for key, value in update_data.items():
        setattr(r, key, value)

    if req.vouchers is not None:
        r.vouchers = to_attachment_maps(req.vouchers)

    r.status = flow.PENDING_REVIEW
    r.GSI1PK = ReimbursementModel.make_gsi1pk(flow.PENDING_REVIEW)
    r.updated_at = datetime.now(timezone.utc).isoformat()
    r.save()
    log_action(current_user["user_id"], _user_name(current_user), "update", "reimbursement", reimburse_id, "更新报销申请")
    return APIResponse(message="报销申请更新成功")


# --- 链路操作 ---------------------------------------------------------------

@router.post("/{reimburse_id}/audit")
def audit_reimbursement(reimburse_id: str, req: ReimbursementAudit, current_user: dict = Depends(get_current_user)):
    """Review/audit reimbursement - 主管审核或财务审核，由当前状态决定。"""
    r = _get_or_404(reimburse_id)

    try:
        step = flow.audit_step_for_status(r.status)
    except flow.TransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    permission = flow.STEPS[step]["permission"]
    if not has_permission(current_user["role"], permission):
        raise HTTPException(
            status_code=403,
            detail=f"当前需要「{flow.step_label(step)}」，你的角色无此权限")

    audit_level = flow.STEPS[step]["audit_level"]
    _advance(r, step, current_user, action=req.action, comments=req.comments)
    r.save()
    log_action(current_user["user_id"], _user_name(current_user), "audit", "reimbursement", reimburse_id, f"审核报销({audit_level}): {req.action} - {req.comments or ''}")
    return APIResponse(message="审核操作成功", data={"status": r.status})


@router.post("/{reimburse_id}/confirm-receipt")
def confirm_receipt(reimburse_id: str, req: ReimbursementReceipt,
                    current_user: dict = Depends(require_permission("reimburse:receipt"))):
    """项目收款确认 - 硬门禁。admin 可 skip=True 强制跳过，但必须填写原因。"""
    r = _get_or_404(reimburse_id)

    contract = None
    if req.skip:
        if not has_permission(current_user["role"], "reimburse:receipt_skip"):
            raise HTTPException(status_code=403, detail="只有管理员可以跳过项目收款确认")
        if not (req.skip_reason or "").strip():
            raise HTTPException(status_code=400, detail="跳过项目收款确认必须填写原因")
    else:
        if not req.contract_id:
            raise HTTPException(status_code=400, detail="请选择本次收款对应的甲方合同")
        if not req.receipt_amount or req.receipt_amount <= 0:
            raise HTTPException(status_code=400, detail="收款金额必须大于0")
        # 合同号以库里的记录为准，不采信前端传值
        contract = _client_contract(req.contract_id, r.project_id)

    comments = f"跳过收款确认: {req.skip_reason}" if req.skip else (
        f"项目收款 ¥{req.receipt_amount} ({contract.contract_no})"
        + (f" {req.note}" if req.note else ""))
    now = _advance(r, flow.CONFIRM_RECEIPT, current_user,
                   action="skipped" if req.skip else "confirmed", comments=comments)

    r.receipt_skipped = bool(req.skip)
    r.receipt_skip_reason = req.skip_reason if req.skip else None
    if not req.skip:
        r.receipt_contract_id = contract.contract_id
        r.receipt_contract_no = contract.contract_no
        r.receipt_amount = req.receipt_amount
        r.receipt_date = req.receipt_date or now[:10]
        r.receipt_note = req.note
    r.receipt_confirmed_at = now
    r.receipt_confirmed_by = current_user["user_id"]
    r.receipt_confirmed_by_name = current_user["display_name"]
    r.save()

    log_action(current_user["user_id"], _user_name(current_user), "confirm_receipt", "reimbursement", reimburse_id, comments)
    return APIResponse(message="跳过项目收款确认" if req.skip else "项目收款确认成功",
                       data={"status": r.status})


@router.post("/{reimburse_id}/create-document")
def create_document(reimburse_id: str, req: ReimbursementDocument,
                    current_user: dict = Depends(require_permission("reimburse:document"))):
    """创建报销单据 - 生成单据号后进入财务审核。"""
    r = _get_or_404(reimburse_id)

    document_no = (req.document_no or "").strip() or flow.generate_document_no()
    now = _advance(r, flow.CREATE_DOCUMENT, current_user, action="created",
                   comments=f"创建单据 {document_no}" + (f" {req.note}" if req.note else ""))

    r.document_no = document_no
    r.document_created_at = now
    r.document_created_by = current_user["user_id"]
    r.document_created_by_name = current_user["display_name"]
    r.save()

    log_action(current_user["user_id"], _user_name(current_user), "create_document", "reimbursement", reimburse_id, f"创建报销单据: {document_no}")
    return APIResponse(message=f"单据 {document_no} 创建成功",
                       data={"status": r.status, "document_no": document_no})


@router.post("/{reimburse_id}/generate-voucher")
def generate_voucher(reimburse_id: str, req: ReimbursementVoucher,
                     current_user: dict = Depends(require_permission("reimburse:voucher"))):
    """生成会计凭证 - 凭证生成后才能付款。"""
    r = _get_or_404(reimburse_id)

    voucher_no = (req.voucher_no or "").strip() or flow.generate_voucher_no()
    now = _advance(r, flow.GENERATE_VOUCHER, current_user, action="generated",
                   comments=f"生成凭证 {voucher_no}" + (f" {req.note}" if req.note else ""))

    r.voucher_no = voucher_no
    r.voucher_generated_at = now
    r.voucher_generated_by = current_user["user_id"]
    r.voucher_generated_by_name = current_user["display_name"]
    if req.voucher_files is not None:
        r.voucher_files = to_attachment_maps(req.voucher_files)
    r.save()

    log_action(current_user["user_id"], _user_name(current_user), "generate_voucher", "reimbursement", reimburse_id, f"生成会计凭证: {voucher_no}")
    return APIResponse(message=f"凭证 {voucher_no} 生成成功",
                       data={"status": r.status, "voucher_no": voucher_no})


@router.post("/{reimburse_id}/pay")
def pay_reimbursement(reimburse_id: str, req: ReimbursementPayment,
                      current_user: dict = Depends(require_permission("reimburse:pay"))):
    """Process reimbursement payment - 需先生成凭证。"""
    r = _get_or_404(reimburse_id)

    _advance(r, flow.PAY, current_user, action="paid",
             comments=f"付款 ¥{req.payment_amount} ({req.payment_method})")
    r.payment_amount = req.payment_amount
    r.payment_method = req.payment_method
    r.payment_time = req.payment_time
    r.payment_status = "paid"
    r.save()

    log_action(current_user["user_id"], _user_name(current_user), "pay", "reimbursement", reimburse_id, f"报销付款: ¥{req.payment_amount} ({req.payment_method})")
    return APIResponse(message="付款成功", data={"status": r.status})


@router.delete("/{reimburse_id}")
def delete_reimbursement(reimburse_id: str, current_user: dict = Depends(require_permission("reimburse:delete"))):
    """Delete reimbursement (admin only)."""
    r = _get_or_404(reimburse_id)
    log_action(current_user["user_id"], _user_name(current_user), "delete", "reimbursement", reimburse_id, "删除报销记录")
    r.delete()
    return APIResponse(message="报销记录删除成功")
