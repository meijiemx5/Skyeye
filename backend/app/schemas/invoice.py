"""Invoice schemas - 批次 + 单张发票。"""
from typing import Optional, List
from pydantic import BaseModel
from .common import AttachmentSchema


class InvoiceRecordCreate(BaseModel):
    """一张发票。tax_rate 接受 13 或 0.13，服务端统一归一化为小数。"""
    invoice_no: Optional[str] = None
    invoice_code: Optional[str] = None
    category: str = "other"  # material, construction, service, other
    tax_rate: Optional[float] = None  # 留空按 category 默认税率
    amount_with_tax: float
    amount_without_tax: Optional[float] = None  # 留空自动换算
    tax_amount: Optional[float] = None          # 留空自动换算
    issue_date: Optional[str] = None
    buyer_name: Optional[str] = None
    seller_name: Optional[str] = None
    remarks: Optional[str] = None
    attachments: Optional[List[dict]] = None


class InvoiceRecordUpdate(BaseModel):
    invoice_no: Optional[str] = None
    invoice_code: Optional[str] = None
    category: Optional[str] = None
    tax_rate: Optional[float] = None
    amount_with_tax: Optional[float] = None
    amount_without_tax: Optional[float] = None
    tax_amount: Optional[float] = None
    issue_date: Optional[str] = None
    buyer_name: Optional[str] = None
    seller_name: Optional[str] = None
    remarks: Optional[str] = None
    attachments: Optional[List[dict]] = None


class InvoiceBatchCreate(BaseModel):
    contract_id: str
    contract_no: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    batch_name: Optional[str] = None
    payment_stage: str = "other"  # advance, progress, final, other
    issue_date: Optional[str] = None
    planned_amount: Optional[float] = None
    status: str = "draft"  # draft, issued, received, void
    remarks: Optional[str] = None
    invoices: Optional[List[InvoiceRecordCreate]] = None  # 可与批次一起提交


class InvoiceBatchUpdate(BaseModel):
    batch_name: Optional[str] = None
    payment_stage: Optional[str] = None
    issue_date: Optional[str] = None
    planned_amount: Optional[float] = None
    status: Optional[str] = None
    remarks: Optional[str] = None


class InvoiceRecordOut(BaseModel):
    invoice_id: str
    batch_id: str
    invoice_no: Optional[str] = None
    invoice_code: Optional[str] = None
    category: str
    tax_rate: float
    amount_with_tax: float
    amount_without_tax: Optional[float] = None
    tax_amount: Optional[float] = None
    issue_date: Optional[str] = None
    buyer_name: Optional[str] = None
    seller_name: Optional[str] = None
    contract_id: Optional[str] = None
    contract_no: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    remarks: Optional[str] = None
    attachments: List[AttachmentSchema] = []
    created_at: str
    updated_at: str


class InvoiceBatchOut(BaseModel):
    batch_id: str
    batch_no: str
    batch_name: Optional[str] = None
    payment_stage: str
    contract_id: Optional[str] = None
    contract_no: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    issue_date: Optional[str] = None
    planned_amount: Optional[float] = None
    total_amount_with_tax: float = 0
    total_amount_without_tax: float = 0
    total_tax_amount: float = 0
    invoice_count: int = 0
    status: str
    remarks: Optional[str] = None
    invoices: List[InvoiceRecordOut] = []
    created_at: str
    updated_at: str
