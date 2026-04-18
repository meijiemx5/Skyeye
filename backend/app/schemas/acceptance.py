"""Acceptance document schemas."""
from typing import Optional, List
from pydantic import BaseModel
from .common import AttachmentSchema


class AcceptanceMemberSchema(BaseModel):
    name: str
    title: Optional[str] = None
    phone: Optional[str] = None


class AcceptanceCreate(BaseModel):
    project_id: str
    project_name: str
    acceptance_date: Optional[str] = None
    acceptance_location: Optional[str] = None
    acceptance_team: List[AcceptanceMemberSchema] = []


class AcceptanceUpdate(BaseModel):
    acceptance_date: Optional[str] = None
    acceptance_location: Optional[str] = None
    acceptance_team: Optional[List[AcceptanceMemberSchema]] = None
    status: Optional[str] = None
    result: Optional[str] = None
    rectification_requirements: Optional[str] = None
    rectification_deadline: Optional[str] = None


class AcceptanceOut(BaseModel):
    acceptance_id: str
    project_id: str
    project_name: str
    acceptance_date: Optional[str] = None
    acceptance_location: Optional[str] = None
    acceptance_team: List[AcceptanceMemberSchema] = []
    status: str
    result: Optional[str] = None
    rectification_requirements: Optional[str] = None
    rectification_deadline: Optional[str] = None
    basic_docs: List[AttachmentSchema] = []
    engineering_docs: List[AttachmentSchema] = []
    compliance_docs: List[AttachmentSchema] = []
    result_docs: List[AttachmentSchema] = []
    other_docs: List[AttachmentSchema] = []
    rectification_docs: List[AttachmentSchema] = []
    created_at: str
    updated_at: str
