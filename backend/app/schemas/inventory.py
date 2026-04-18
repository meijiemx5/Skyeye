"""Inventory schemas."""
from typing import Optional, List
from pydantic import BaseModel
from .common import AttachmentSchema


class MaterialCreate(BaseModel):
    material_name: str
    category: str  # equipment, cable, accessory, tool, other
    specification: Optional[str] = None
    brand: Optional[str] = None
    unit: str
    unit_price: Optional[float] = None
    stock_quantity: float = 0
    min_stock_threshold: Optional[float] = None
    warehouse_location: Optional[str] = None
    shelf_location: Optional[str] = None
    expiry_date: Optional[str] = None
    responsible_person: Optional[str] = None


class MaterialUpdate(BaseModel):
    material_name: Optional[str] = None
    category: Optional[str] = None
    specification: Optional[str] = None
    brand: Optional[str] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    min_stock_threshold: Optional[float] = None
    warehouse_location: Optional[str] = None
    shelf_location: Optional[str] = None
    expiry_date: Optional[str] = None
    responsible_person: Optional[str] = None


class MaterialOut(BaseModel):
    material_id: str
    material_name: str
    category: str
    specification: Optional[str] = None
    brand: Optional[str] = None
    unit: str
    unit_price: Optional[float] = None
    stock_quantity: float
    min_stock_threshold: Optional[float] = None
    warehouse_location: Optional[str] = None
    shelf_location: Optional[str] = None
    expiry_date: Optional[str] = None
    responsible_person: Optional[str] = None
    stock_status: str
    created_at: str
    updated_at: str


class StockInCreate(BaseModel):
    material_id: str
    quantity: float
    unit_price: Optional[float] = None
    supplier_name: Optional[str] = None
    record_date: str


class StockOutCreate(BaseModel):
    material_id: str
    quantity: float
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    requester_name: Optional[str] = None
    purpose: Optional[str] = None
    record_date: str


class StockAdjustmentCreate(BaseModel):
    material_id: str
    actual_quantity: float
    adjustment_reason: Optional[str] = None
    record_date: str


class StockRecordOut(BaseModel):
    record_id: str
    material_id: str
    material_name: str
    record_type: str
    quantity: float
    unit_price: Optional[float] = None
    supplier_name: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    requester_name: Optional[str] = None
    purpose: Optional[str] = None
    system_quantity: Optional[float] = None
    actual_quantity: Optional[float] = None
    adjustment_reason: Optional[str] = None
    record_date: str
    attachments: List[AttachmentSchema] = []
    created_at: str
