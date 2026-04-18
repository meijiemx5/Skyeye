"""Project schemas."""
from typing import Optional
from pydantic import BaseModel


class ProjectCreate(BaseModel):
    project_name: str
    project_manager_id: Optional[str] = None
    project_manager_name: Optional[str] = None
    client_name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    address: Optional[str] = None


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
    created_at: str
    updated_at: str
