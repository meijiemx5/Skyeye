"""Common Pydantic schemas."""
from typing import Optional, List
from pydantic import BaseModel


class APIResponse(BaseModel):
    """Standard API response."""
    success: bool = True
    message: str = "操作成功"
    data: Optional[dict | list] = None
    total: Optional[int] = None


class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = 1
    page_size: int = 20


class AttachmentSchema(BaseModel):
    """Attachment schema."""
    file_id: str
    file_name: str
    file_type: str
    file_size: int
    s3_key: str
    upload_time: str
    uploaded_by: Optional[str] = None


class PaymentNodeSchema(BaseModel):
    """Payment node schema."""
    node_name: str
    percentage: float
    amount: float
    planned_date: Optional[str] = None
    actual_date: Optional[str] = None
    status: str = "pending"
