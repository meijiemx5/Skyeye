"""Reimbursement schemas."""
from typing import Optional, List
from pydantic import BaseModel
from .common import AttachmentSchema


class AuditLogSchema(BaseModel):
    auditor_id: str
    auditor_name: str
    audit_time: str
    action: str  # approved, rejected
    comments: Optional[str] = None
    audit_level: str  # manager, finance


class ReimbursementCreate(BaseModel):
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    amount_with_tax: float
    amount_without_tax: Optional[float] = None
    expense_type: str  # material, travel, equipment_rental, other
    description: str
    expense_date: str
    vouchers: Optional[List[dict]] = None


class ReimbursementUpdate(BaseModel):
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    amount_with_tax: Optional[float] = None
    amount_without_tax: Optional[float] = None
    expense_type: Optional[str] = None
    description: Optional[str] = None
    expense_date: Optional[str] = None
    vouchers: Optional[List[dict]] = None


class ReimbursementAudit(BaseModel):
    action: str  # approved, rejected
    comments: Optional[str] = None


class ReimbursementPayment(BaseModel):
    payment_amount: float
    payment_method: str  # bank_transfer, cash
    payment_time: str


class ReimbursementOut(BaseModel):
    reimburse_id: str
    applicant_id: str
    applicant_name: str
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    amount_with_tax: float
    amount_without_tax: Optional[float] = None
    expense_type: str
    description: str
    expense_date: str
    status: str
    audit_logs: List[AuditLogSchema] = []
    current_reviewer_id: Optional[str] = None
    current_reviewer_name: Optional[str] = None
    payment_amount: Optional[float] = None
    payment_method: Optional[str] = None
    payment_time: Optional[str] = None
    payment_status: Optional[str] = None
    payment_failure_reason: Optional[str] = None
    vouchers: List[AttachmentSchema] = []
    payment_receipt: List[AttachmentSchema] = []
    created_at: str
    updated_at: str
