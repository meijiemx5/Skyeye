"""Audit logging service - records user operations."""
import uuid
from datetime import datetime, timezone
from ..models.audit_log import AuditLogModel


def log_action(
    user_id: str,
    user_name: str,
    action: str,
    resource_type: str,
    resource_id: str = None,
    detail: str = None,
    ip_address: str = None,
):
    """Record an audit log entry."""
    try:
        log_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        ts = now.isoformat()

        log = AuditLogModel()
        log.PK = AuditLogModel.make_pk(date_str)
        log.SK = AuditLogModel.make_sk(ts, log_id)
        log.GSI1PK = AuditLogModel.make_gsi1pk(user_id)
        log.GSI1SK = f"{ts}#{log_id}"
        log.entity_type = "audit_log"
        log.log_id = log_id
        log.user_id = user_id
        log.user_name = user_name
        log.action = action
        log.resource_type = resource_type
        log.resource_id = resource_id
        log.detail = detail
        log.ip_address = ip_address
        log.timestamp = ts
        log.created_at = ts
        log.updated_at = ts
        log.save()
    except Exception as e:
        print(f"⚠️ Audit log error: {e}")
