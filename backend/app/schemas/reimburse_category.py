"""Reimbursement category schemas."""
from typing import Optional, List
from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str
    parent_id: Optional[str] = None
    sort_order: Optional[int] = 0
    code: Optional[str] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    code: Optional[str] = None


class CategoryOut(BaseModel):
    category_id: str
    name: str
    parent_id: Optional[str] = None
    level: int
    sort_order: int = 0
    is_active: bool = True
    code: Optional[str] = None
    children: List["CategoryOut"] = []


CategoryOut.model_rebuild()
