"""Audit log router - view operation logs."""
from fastapi import APIRouter, Depends, Query
from typing import Optional

from ..models.audit_log import AuditLogModel
from ..schemas.common import APIResponse
from ..utils.auth import get_current_user, require_roles

router = APIRouter(prefix="/api/audit-logs", tags=["操作日志"])


@router.get("")
def list_audit_logs(
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_roles("admin"))
):
    """List audit logs (admin only)."""
    results = list(AuditLogModel.scan(filter_condition=AuditLogModel.entity_type == "audit_log"))

    # In-memory filtering (small dataset)
    if user_id:
        results = [r for r in results if r.user_id == user_id]
    if action:
        results = [r for r in results if r.action == action]
    if resource_type:
        results = [r for r in results if r.resource_type == resource_type]
    if date:
        results = [r for r in results if r.timestamp and r.timestamp.startswith(date)]

    # Sort by timestamp descending
    results.sort(key=lambda r: r.timestamp or "", reverse=True)

    total = len(results)
    start = (page - 1) * page_size
    results = results[start:start + page_size]

    data = [
        {
            "log_id": r.log_id,
            "user_id": r.user_id,
            "user_name": r.user_name,
            "action": r.action,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "detail": r.detail,
            "ip_address": r.ip_address,
            "timestamp": r.timestamp,
        }
        for r in results
    ]
    return APIResponse(data=data, total=total)
