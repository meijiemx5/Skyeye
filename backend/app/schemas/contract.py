"""Contract schemas."""
from typing import Optional, List
from pydantic import BaseModel
from .common import AttachmentSchema, PaymentNodeSchema


class ContractCreate(BaseModel):
    contract_name: str
    contract_type: str  # client, supplier, construction
    contract_no: Optional[str] = None  # auto-generated if empty
    party_name: str
    party_contact: Optional[str] = None
    party_phone: Optional[str] = None
    party_address: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    status: str = "draft"
    sign_date: Optional[str] = None
    amount_with_tax: Optional[float] = None
    amount_without_tax: Optional[float] = None
    work_start_date: Optional[str] = None
    work_end_date: Optional[str] = None
    payment_nodes: List[PaymentNodeSchema] = []
    remarks: Optional[str] = None
    special_terms: Optional[str] = None
    penalty_clause: Optional[str] = None


class ContractUpdate(BaseModel):
    contract_name: Optional[str] = None
    contract_no: Optional[str] = None
    party_name: Optional[str] = None
    party_contact: Optional[str] = None
    party_phone: Optional[str] = None
    party_address: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    status: Optional[str] = None
    sign_date: Optional[str] = None
    amount_with_tax: Optional[float] = None
    amount_without_tax: Optional[float] = None
    paid_amount: Optional[float] = None
    work_start_date: Optional[str] = None
    work_end_date: Optional[str] = None
    payment_nodes: Optional[List[PaymentNodeSchema]] = None
    remarks: Optional[str] = None
    special_terms: Optional[str] = None
    penalty_clause: Optional[str] = None


class ContractQuery(BaseModel):
    contract_type: Optional[str] = None
    contract_no: Optional[str] = None
    contract_name: Optional[str] = None
    party_name: Optional[str] = None
    status: Optional[str] = None
    sign_date_from: Optional[str] = None
    sign_date_to: Optional[str] = None
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    project_id: Optional[str] = None
    page: int = 1
    page_size: int = 20


class ContractOut(BaseModel):
    contract_id: str
    contract_no: str
    contract_name: str
    contract_type: str
    party_name: str
    party_contact: Optional[str] = None
    party_phone: Optional[str] = None
    party_address: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    status: str
    sign_date: Optional[str] = None
    amount_with_tax: Optional[float] = None
    amount_without_tax: Optional[float] = None
    paid_amount: float = 0
    work_start_date: Optional[str] = None
    work_end_date: Optional[str] = None
    payment_nodes: List[PaymentNodeSchema] = []
    attachments: List[AttachmentSchema] = []
    remarks: Optional[str] = None
    special_terms: Optional[str] = None
    penalty_clause: Optional[str] = None
    created_at: str
    updated_at: str
