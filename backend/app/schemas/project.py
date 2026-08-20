"""Project schemas."""
from typing import Optional, List
from pydantic import BaseModel
from .common import AttachmentSchema


class ProjectCreate(BaseModel):
    project_name: str
    project_manager_id: Optional[str] = None
    project_manager_name: Optional[str] = None
    client_name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    address: Optional[str] = None
    budget_amount: Optional[float] = None
    quote_amount: Optional[float] = None
    budget_docs: Optional[List[dict]] = None
    quote_docs: Optional[List[dict]] = None


class ProjectUpdate(BaseModel):
    project_name: Optional[str] = None
    project_manager_id: Optional[str] = None
    project_manager_name: Optional[str] = None
    client_name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    actual_end_date: Optional[str] = None
    address: Optional[str] = None
    budget_amount: Optional[float] = None
    quote_amount: Optional[float] = None
    budget_docs: Optional[List[dict]] = None
    quote_docs: Optional[List[dict]] = None


class ProjectOut(BaseModel):
    project_id: str
    project_name: str
    project_manager_id: Optional[str] = None
    project_manager_name: Optional[str] = None
    client_name: Optional[str] = None
    description: Optional[str] = None
    status: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    actual_end_date: Optional[str] = None
    address: Optional[str] = None
    budget_amount: Optional[float] = None
    quote_amount: Optional[float] = None
    budget_docs: List[AttachmentSchema] = []
    quote_docs: List[AttachmentSchema] = []
    created_at: str
    updated_at: str


class ProjectOption(BaseModel):
    """精简项目选项 - 供无项目查看权限的角色填下拉框使用。"""
    project_id: str
    project_name: str
    status: str
