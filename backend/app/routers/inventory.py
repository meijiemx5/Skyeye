"""Inventory management router."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
from pynamodb.exceptions import DoesNotExist
from typing import Optional

from ..models.inventory import MaterialModel, StockRecordModel
from ..schemas.inventory import MaterialCreate, MaterialUpdate, StockInCreate, StockOutCreate, StockAdjustmentCreate
from ..schemas.common import APIResponse
from ..utils.auth import get_current_user, require_roles
from ..services.audit import log_action

router = APIRouter(prefix="/api/inventory", tags=["库存管理"])


def _material_to_dict(m):
    return {
        "material_id": m.material_id, "material_name": m.material_name,
        "category": m.category, "specification": m.specification,
        "brand": m.brand, "unit": m.unit, "unit_price": m.unit_price,
        "stock_quantity": m.stock_quantity, "min_stock_threshold": m.min_stock_threshold,
        "warehouse_location": m.warehouse_location, "shelf_location": m.shelf_location,
        "expiry_date": m.expiry_date, "responsible_person": m.responsible_person,
        "stock_status": m.stock_status, "created_at": m.created_at, "updated_at": m.updated_at,
    }


def _record_to_dict(r):
    return {
        "record_id": r.record_id, "material_id": r.material_id,
        "material_name": r.material_name, "record_type": r.record_type,
        "quantity": r.quantity, "unit_price": r.unit_price,
        "supplier_name": r.supplier_name, "project_id": r.project_id,
        "project_name": r.project_name, "requester_name": r.requester_name,
        "purpose": r.purpose, "system_quantity": r.system_quantity,
        "actual_quantity": r.actual_quantity, "adjustment_reason": r.adjustment_reason,
        "record_date": r.record_date, "created_at": r.created_at,
        "attachments": [{"file_id": a.file_id, "file_name": a.file_name, "file_type": a.file_type,
                         "file_size": a.file_size, "s3_key": a.s3_key, "upload_time": a.upload_time}
                        for a in (r.attachments or [])],
    }


def _update_stock_status(material):
    """Update stock status based on quantity and threshold."""
    if material.stock_quantity <= 0:
        material.stock_status = "out_of_stock"
    elif material.min_stock_threshold and material.stock_quantity <= material.min_stock_threshold:
        material.stock_status = "warning"
    else:
        material.stock_status = "normal"


# === Material CRUD ===

@router.get("/materials")
def list_materials(
    category: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    stock_status: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """List materials."""
    results = list(MaterialModel.scan(filter_condition=MaterialModel.entity_type == "material"))
    if category:
        results = [r for r in results if r.category == category]
    if stock_status:
        results = [r for r in results if r.stock_status == stock_status]
    if keyword:
        results = [r for r in results if keyword in (r.material_name or "") or keyword in (r.specification or "") or keyword in (r.brand or "")]
    data = [_material_to_dict(m) for m in results]
    return APIResponse(data=data, total=len(data))


@router.get("/materials/warnings")
def get_stock_warnings(current_user: dict = Depends(get_current_user)):
    """Get materials with low stock warnings."""
    results = list(MaterialModel.scan(filter_condition=MaterialModel.entity_type == "material"))
    warnings = [_material_to_dict(m) for m in results if m.stock_status in ("warning", "out_of_stock")]
    return APIResponse(data=warnings, total=len(warnings))


@router.get("/materials/statistics")
def material_statistics(current_user: dict = Depends(get_current_user)):
    """Get inventory statistics."""
    materials = list(MaterialModel.scan(filter_condition=MaterialModel.entity_type == "material"))
    records = list(StockRecordModel.scan(filter_condition=StockRecordModel.entity_type == "stock_record"))
    
    total_value = sum((m.stock_quantity or 0) * (m.unit_price or 0) for m in materials)
    total_in = sum(r.quantity for r in records if r.record_type == "in")
    total_out = sum(r.quantity for r in records if r.record_type == "out")
    
    by_category = {}
    for m in materials:
        cat = m.category
        if cat not in by_category:
            by_category[cat] = {"count": 0, "quantity": 0, "value": 0}
        by_category[cat]["count"] += 1
        by_category[cat]["quantity"] += m.stock_quantity or 0
        by_category[cat]["value"] += (m.stock_quantity or 0) * (m.unit_price or 0)
    
    return APIResponse(data={
        "total_materials": len(materials),
        "total_value": total_value,
        "total_in": total_in,
        "total_out": total_out,
        "warning_count": len([m for m in materials if m.stock_status == "warning"]),
        "out_of_stock_count": len([m for m in materials if m.stock_status == "out_of_stock"]),
        "by_category": by_category,
    })


@router.get("/materials/{material_id}")
def get_material(material_id: str, current_user: dict = Depends(get_current_user)):
    """Get material detail."""
    try:
        m = MaterialModel.get(MaterialModel.make_pk(material_id), MaterialModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="物料不存在")
    return APIResponse(data=_material_to_dict(m))


@router.post("/materials")
def create_material(req: MaterialCreate, current_user: dict = Depends(require_roles("admin", "procurement", "warehouse"))):
    """Create material."""
    material_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    
    m = MaterialModel()
    m.PK = MaterialModel.make_pk(material_id)
    m.SK = MaterialModel.make_sk()
    m.GSI1PK = MaterialModel.make_gsi1pk(req.category)
    m.GSI1SK = f"MATERIAL#{material_id}"
    m.entity_type = "material"
    m.material_id = material_id
    m.material_name = req.material_name
    m.category = req.category
    m.specification = req.specification
    m.brand = req.brand
    m.unit = req.unit
    m.unit_price = req.unit_price
    m.stock_quantity = req.stock_quantity
    m.min_stock_threshold = req.min_stock_threshold
    m.warehouse_location = req.warehouse_location
    m.shelf_location = req.shelf_location
    m.expiry_date = req.expiry_date
    m.responsible_person = req.responsible_person
    m.created_at = now
    m.updated_at = now
    m.created_by = current_user["user_id"]
    _update_stock_status(m)
    m.save()
    log_action(current_user["user_id"], f"{current_user['username']}({current_user['display_name']})", "create", "material", material_id, f"创建物料: {req.material_name}")
    return APIResponse(message="物料创建成功", data={"material_id": material_id})


@router.put("/materials/{material_id}")
def update_material(material_id: str, req: MaterialUpdate, current_user: dict = Depends(require_roles("admin", "procurement", "warehouse"))):
    """Update material."""
    try:
        m = MaterialModel.get(MaterialModel.make_pk(material_id), MaterialModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="物料不存在")
    
    update_data = req.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(m, key, value)
    
    _update_stock_status(m)
    m.updated_at = datetime.now(timezone.utc).isoformat()
    m.updated_by = current_user["user_id"]
    m.save()
    log_action(current_user["user_id"], f"{current_user['username']}({current_user['display_name']})", "update", "material", material_id, f"更新物料: {m.material_name}")
    return APIResponse(message="物料更新成功")


@router.delete("/materials/{material_id}")
def delete_material(material_id: str, current_user: dict = Depends(require_roles("admin"))):
    """Delete material."""
    try:
        m = MaterialModel.get(MaterialModel.make_pk(material_id), MaterialModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="物料不存在")
    log_action(current_user["user_id"], f"{current_user['username']}({current_user['display_name']})", "delete", "material", material_id, f"删除物料: {m.material_name}")
    m.delete()
    return APIResponse(message="物料删除成功")


# === Stock Records ===

@router.get("/records")
def list_stock_records(
    material_id: Optional[str] = Query(None),
    record_type: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """List stock records."""
    results = list(StockRecordModel.scan(filter_condition=StockRecordModel.entity_type == "stock_record"))
    if material_id:
        results = [r for r in results if r.material_id == material_id]
    if record_type:
        results = [r for r in results if r.record_type == record_type]
    data = [_record_to_dict(r) for r in results]
    return APIResponse(data=data, total=len(data))


@router.post("/stock-in")
def stock_in(req: StockInCreate, current_user: dict = Depends(require_roles("admin", "procurement"))):
    """Record stock in."""
    try:
        material = MaterialModel.get(MaterialModel.make_pk(req.material_id), MaterialModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="物料不存在")
    
    record_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    
    r = StockRecordModel()
    r.PK = StockRecordModel.make_pk(req.material_id)
    r.SK = StockRecordModel.make_sk(record_id)
    r.entity_type = "stock_record"
    r.record_id = record_id
    r.material_id = req.material_id
    r.material_name = material.material_name
    r.record_type = "in"
    r.quantity = req.quantity
    r.unit_price = req.unit_price
    r.supplier_name = req.supplier_name
    r.record_date = req.record_date
    r.created_at = now
    r.updated_at = now
    r.created_by = current_user["user_id"]
    r.save()
    
    # Update material stock
    material.stock_quantity = (material.stock_quantity or 0) + req.quantity
    if req.unit_price:
        material.unit_price = req.unit_price
    _update_stock_status(material)
    material.updated_at = now
    material.save()
    
    log_action(current_user["user_id"], f"{current_user['username']}({current_user['display_name']})", "stock_in", "inventory", record_id, f"入库: {material.material_name} x{req.quantity}")
    return APIResponse(message="入库成功", data={"record_id": record_id})


@router.post("/stock-out")
def stock_out(req: StockOutCreate, current_user: dict = Depends(require_roles("admin", "procurement"))):
    """Record stock out."""
    try:
        material = MaterialModel.get(MaterialModel.make_pk(req.material_id), MaterialModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="物料不存在")
    
    if (material.stock_quantity or 0) < req.quantity:
        raise HTTPException(status_code=400, detail=f"库存不足，当前库存: {material.stock_quantity}")
    
    record_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    
    r = StockRecordModel()
    r.PK = StockRecordModel.make_pk(req.material_id)
    r.SK = StockRecordModel.make_sk(record_id)
    if req.project_id:
        r.GSI2PK = StockRecordModel.make_gsi2pk(req.project_id)
        r.GSI2SK = f"STOCK#{record_id}"
    r.entity_type = "stock_record"
    r.record_id = record_id
    r.material_id = req.material_id
    r.material_name = material.material_name
    r.record_type = "out"
    r.quantity = req.quantity
    r.unit_price = material.unit_price  # save current unit price for cost calculation
    r.project_id = req.project_id
    r.project_name = req.project_name
    r.requester_name = req.requester_name
    r.purpose = req.purpose
    r.record_date = req.record_date
    r.created_at = now
    r.updated_at = now
    r.created_by = current_user["user_id"]
    r.save()
    
    # Update material stock
    material.stock_quantity = (material.stock_quantity or 0) - req.quantity
    _update_stock_status(material)
    material.updated_at = now
    material.save()
    
    log_action(current_user["user_id"], f"{current_user['username']}({current_user['display_name']})", "stock_out", "inventory", record_id, f"出库: {material.material_name} x{req.quantity} → {req.project_name or ''}")
    return APIResponse(message="出库成功", data={"record_id": record_id})


@router.post("/adjustment")
def stock_adjustment(req: StockAdjustmentCreate, current_user: dict = Depends(require_roles("admin", "warehouse"))):
    """Inventory adjustment (盘点)."""
    try:
        material = MaterialModel.get(MaterialModel.make_pk(req.material_id), MaterialModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="物料不存在")
    
    record_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    
    r = StockRecordModel()
    r.PK = StockRecordModel.make_pk(req.material_id)
    r.SK = StockRecordModel.make_sk(record_id)
    r.entity_type = "stock_record"
    r.record_id = record_id
    r.material_id = req.material_id
    r.material_name = material.material_name
    r.record_type = "adjustment"
    r.quantity = abs(req.actual_quantity - (material.stock_quantity or 0))
    r.system_quantity = material.stock_quantity or 0
    r.actual_quantity = req.actual_quantity
    r.adjustment_reason = req.adjustment_reason
    r.record_date = req.record_date
    r.created_at = now
    r.updated_at = now
    r.created_by = current_user["user_id"]
    r.save()
    
    # Update material stock
    material.stock_quantity = req.actual_quantity
    _update_stock_status(material)
    material.updated_at = now
    material.save()
    
    log_action(current_user["user_id"], f"{current_user['username']}({current_user['display_name']})", "adjustment", "inventory", record_id, f"盘点: {material.material_name} {material.stock_quantity}→{req.actual_quantity}")
    return APIResponse(message="盘点调整成功", data={"record_id": record_id})
