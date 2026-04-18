"""User schemas."""
from typing import Optional
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str
    role: str  # admin, finance, project_manager, procurement, construction, warehouse
    phone: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None


class ChangePassword(BaseModel):
    old_password: str
    new_password: str


class UserOut(BaseModel):
    user_id: str
    username: str
    display_name: str
    role: str
    phone: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    is_active: bool
    created_at: str
