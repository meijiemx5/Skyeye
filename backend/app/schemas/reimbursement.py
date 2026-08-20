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
    expense_type: str  # category_id (sub if any else parent); legacy: material/travel/...
    expense_category_id: Optional[str] = None
    expense_subcategory_id: Optional[str] = None
    description: str
    expense_date: str
    vouchers: Optional[List[dict]] = None


class ReimbursementUpdate(BaseModel):
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    amount_with_tax: Optional[float] = None
    amount_without_tax: Optional[float] = None
    expense_type: Optional[str] = None
    expense_category_id: Optional[str] = None
    expense_subcategory_id: Optional[str] = None
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


class ReimbursementReceipt(BaseModel):
    """项目收款确认 - 硬门禁; admin 可 skip=True 强制跳过但必须写原因。"""
    contract_id: Optional[str] = None
    contract_no: Optional[str] = None
    receipt_amount: Optional[float] = None
    receipt_date: Optional[str] = None
    note: Optional[str] = None
    skip: bool = False
    skip_reason: Optional[str] = None


class ReimbursementDocument(BaseModel):
    """创建报销单据 - 单据号留空则自动生成 BX-YYYYMMDD-XXXX。"""
    document_no: Optional[str] = None
    note: Optional[str] = None


class ReimbursementVoucher(BaseModel):
    """生成会计凭证 - 凭证号留空则自动生成 PZ-YYYYMMDD-XXXX。"""
    voucher_no: Optional[str] = None
    note: Optional[str] = None
    voucher_files: Optional[List[dict]] = None


class ReimbursementOut(BaseModel):
    reimburse_id: str
    applicant_id: str
    applicant_name: str
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    amount_with_tax: float
    amount_without_tax: Optional[float] = None
    expense_type: str
    expense_category_id: Optional[str] = None
    expense_subcategory_id: Optional[str] = None
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
    # 链路留痕: 项目收款 → 单据 → 凭证
    receipt_contract_id: Optional[str] = None
    receipt_contract_no: Optional[str] = None
    receipt_amount: Optional[float] = None
    receipt_date: Optional[str] = None
    receipt_note: Optional[str] = None
    receipt_confirmed_at: Optional[str] = None
    receipt_confirmed_by_name: Optional[str] = None
    receipt_skipped: Optional[bool] = None
    receipt_skip_reason: Optional[str] = None
    document_no: Optional[str] = None
    document_created_at: Optional[str] = None
    document_created_by_name: Optional[str] = None
    voucher_no: Optional[str] = None
    voucher_generated_at: Optional[str] = None
    voucher_generated_by_name: Optional[str] = None
    voucher_files: List[AttachmentSchema] = []
    created_at: str
    updated_at: str
