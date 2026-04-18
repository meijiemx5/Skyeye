"""Audit log model - records all user operations.

PK: AUDIT#{date}
SK: {timestamp}#{log_id}
GSI1PK: AUDIT_USER#{user_id}
GSI1SK: {timestamp}#{log_id}
"""
from pynamodb.attributes import UnicodeAttribute
from .base import BaseModel


class AuditLogModel(BaseModel):
    """Audit log entity - records all user operations."""
    log_id = UnicodeAttribute()
    user_id = UnicodeAttribute()
    user_name = UnicodeAttribute()
    action = UnicodeAttribute()  # create, update, delete, login, logout
    resource_type = UnicodeAttribute()  # contract, reimbursement, acceptance, inventory, user
    resource_id = UnicodeAttribute(null=True)
    detail = UnicodeAttribute(null=True)
    ip_address = UnicodeAttribute(null=True)
    timestamp = UnicodeAttribute()

    @staticmethod
    def make_pk(date: str) -> str:
        return f"AUDIT#{date}"

    @staticmethod
    def make_sk(timestamp: str, log_id: str) -> str:
        return f"{timestamp}#{log_id}"

    @staticmethod
    def make_gsi1pk(user_id: str) -> str:
        return f"AUDIT_USER#{user_id}"
