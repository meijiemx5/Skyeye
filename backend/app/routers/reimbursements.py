"""Reimbursement router - full workflow: apply -> review -> payment."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
from pynamodb.exceptions import DoesNotExist
from typing import Optional

from ..models.reimbursement import ReimbursementModel, AuditLogMap
from ..schemas.reimbursement import ReimbursementCreate, ReimbursementUpdate, ReimbursementAudit, ReimbursementPayment
from ..schemas.common import APIResponse
from ..utils.auth import get_current_user, require_roles

router = APIRouter(prefix="/api/reimbursements", tags=["报销管理"])


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
        "description": r.description,
        "expense_date": r.expense_date,
        "status": r.status,
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
        "vouchers": [
            {"file_id": a.file_id, "file_name": a.file_name, "file_type": a.file_type,
             "file_size": a.file_size, "s3_key": a.s3_key, "upload_time": a.upload_time}
            for a in (r.vouchers or [])
        ],
        "payment_receipt": [
            {"file_id": a.file_id, "file_name": a.file_name, "file_type": a.file_type,
             "file_size": a.file_size, "s3_key": a.s3_key, "upload_time": a.upload_time}
            for a in (r.payment_receipt or [])
        ],
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


@router.get("")
def list_reimbursements(
    status: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    expense_type: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """List reimbursements."""
    results = list(ReimbursementModel.scan(filter_condition=ReimbursementModel.entity_type == "reimbursement"))
    
    if status:
        results = [r for r in results if r.status == status]
    if project_id:
        results = [r for r in results if r.project_id == project_id]
    if expense_type:
        results = [r for r in results if r.expense_type == expense_type]
    
    # Role-based filtering
    role = current_user["role"]
    uid = current_user["user_id"]
    if role == "construction":
        results = [r for r in results if r.applicant_id == uid]
    elif role == "project_manager":
        results = [r for r in results if r.applicant_id == uid or r.current_reviewer_id == uid]
    # finance and admin can see all
    
    data = [_reimburse_to_dict(r) for r in results]
    return APIResponse(data=data, total=len(data))


@router.get("/{reimburse_id}")
def get_reimbursement(reimburse_id: str, current_user: dict = Depends(get_current_user)):
    """Get reimbursement detail."""
    try:
        r = ReimbursementModel.get(ReimbursementModel.make_pk(reimburse_id), ReimbursementModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="报销记录不存在")
    return APIResponse(data=_reimburse_to_dict(r))


@router.post("")
def create_reimbursement(req: ReimbursementCreate, current_user: dict = Depends(get_current_user)):
    """Submit reimbursement application."""
    reimburse_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    
    r = ReimbursementModel()
    r.PK = ReimbursementModel.make_pk(reimburse_id)
    r.SK = ReimbursementModel.make_sk()
    r.GSI1PK = ReimbursementModel.make_gsi1pk("pending_review")
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
    r.expense_type = req.expense_type
    r.description = req.description
    r.expense_date = req.expense_date
    r.status = "pending_review"
    r.created_at = now
    r.updated_at = now
    r.created_by = current_user["user_id"]
    r.save()
    
    return APIResponse(message="报销申请提交成功", data={"reimburse_id": reimburse_id})


@router.put("/{reimburse_id}")
def update_reimbursement(reimburse_id: str, req: ReimbursementUpdate, current_user: dict = Depends(get_current_user)):
    """Update reimbursement (only if rejected/pending)."""
    try:
        r = ReimbursementModel.get(ReimbursementModel.make_pk(reimburse_id), ReimbursementModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="报销记录不存在")
    
    if r.status not in ("pending_review", "rejected"):
        raise HTTPException(status_code=400, detail="当前状态不允许修改")
    if r.applicant_id != current_user["user_id"] and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="只能修改自己的报销申请")
    
    update_data = req.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(r, key, value)
    
    r.status = "pending_review"
    r.GSI1PK = ReimbursementModel.make_gsi1pk("pending_review")
    r.updated_at = datetime.now(timezone.utc).isoformat()
    r.save()
    
    return APIResponse(message="报销申请更新成功")


@router.post("/{reimburse_id}/audit")
def audit_reimbursement(reimburse_id: str, req: ReimbursementAudit, current_user: dict = Depends(require_roles("admin", "project_manager", "finance"))):
    """Review/audit reimbursement."""
    try:
        r = ReimbursementModel.get(ReimbursementModel.make_pk(reimburse_id), ReimbursementModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="报销记录不存在")
    
    now = datetime.now(timezone.utc).isoformat()
    role = current_user["role"]
    
    # Determine audit level
    if role in ("project_manager", "admin") and r.status == "pending_review":
        audit_level = "manager"
    elif role in ("finance", "admin") and r.status == "manager_approved":
        audit_level = "finance"
    else:
        raise HTTPException(status_code=400, detail="当前状态不允许此角色审核")
    
    # Create audit log
    log = AuditLogMap()
    log.auditor_id = current_user["user_id"]
    log.auditor_name = current_user["display_name"]
    log.audit_time = now
    log.action = req.action
    log.comments = req.comments
    log.audit_level = audit_level
    
    logs = list(r.audit_logs or [])
    logs.append(log)
    r.audit_logs = logs
    
    if req.action == "approved":
        if audit_level == "manager":
            r.status = "manager_approved"
        elif audit_level == "finance":
            r.status = "finance_approved"
    elif req.action == "rejected":
        r.status = "rejected"
    
    r.GSI1PK = ReimbursementModel.make_gsi1pk(r.status)
    r.updated_at = now
    r.save()
    
    return APIResponse(message="审核操作成功")


@router.post("/{reimburse_id}/pay")
def pay_reimbursement(reimburse_id: str, req: ReimbursementPayment, current_user: dict = Depends(require_roles("admin", "finance"))):
    """Process reimbursement payment."""
    try:
        r = ReimbursementModel.get(ReimbursementModel.make_pk(reimburse_id), ReimbursementModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="报销记录不存在")
    
    if r.status != "finance_approved":
        raise HTTPException(status_code=400, detail="只有财务审核通过后才能付款")
    
    now = datetime.now(timezone.utc).isoformat()
    r.payment_amount = req.payment_amount
    r.payment_method = req.payment_method
    r.payment_time = req.payment_time
    r.payment_status = "paid"
    r.status = "paid"
    r.GSI1PK = ReimbursementModel.make_gsi1pk("paid")
    r.updated_at = now
    r.save()
    
    return APIResponse(message="付款成功")


@router.delete("/{reimburse_id}")
def delete_reimbursement(reimburse_id: str, current_user: dict = Depends(require_roles("admin"))):
    """Delete reimbursement (admin only)."""
    try:
        r = ReimbursementModel.get(ReimbursementModel.make_pk(reimburse_id), ReimbursementModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="报销记录不存在")
    r.delete()
    return APIResponse(message="报销记录删除成功")
