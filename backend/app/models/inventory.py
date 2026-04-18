"""Inventory model - material management with stock in/out tracking.

Material: PK: MATERIAL#{material_id}, SK: META
Stock Record: PK: MATERIAL#{material_id}, SK: STOCK#{record_id}
GSI1PK: MATERIAL_CATEGORY#{category}
GSI1SK: MATERIAL#{material_id}
GSI2PK: PROJECT#{project_id}  (for out-stock records)
GSI2SK: STOCK#{record_id}
"""
from pynamodb.attributes import UnicodeAttribute, NumberAttribute, BooleanAttribute
from .base import BaseModel, AttachmentMap
from pynamodb.attributes import ListAttribute


class MaterialModel(BaseModel):
    """Material/inventory item entity."""
    material_id = UnicodeAttribute()
    material_name = UnicodeAttribute()
    category = UnicodeAttribute()  # equipment, cable, accessory, tool, other
    specification = UnicodeAttribute(null=True)  # 规格型号
    brand = UnicodeAttribute(null=True)
    unit = UnicodeAttribute()  # 个, 米, 套, etc.
    unit_price = NumberAttribute(null=True)
    stock_quantity = NumberAttribute(default=0)
    min_stock_threshold = NumberAttribute(null=True)  # 最低库存阈值
    warehouse_location = UnicodeAttribute(null=True)  # 仓库编号/货架位置
    shelf_location = UnicodeAttribute(null=True)
    expiry_date = UnicodeAttribute(null=True)
    responsible_person = UnicodeAttribute(null=True)
    stock_status = UnicodeAttribute(default="normal")  # normal, warning, out_of_stock

    @staticmethod
    def make_pk(material_id: str) -> str:
        return f"MATERIAL#{material_id}"

    @staticmethod
    def make_sk() -> str:
        return "META"

    @staticmethod
    def make_gsi1pk(category: str) -> str:
        return f"MATERIAL_CATEGORY#{category}"


class StockRecordModel(BaseModel):
    """Stock in/out record entity."""
    record_id = UnicodeAttribute()
    material_id = UnicodeAttribute()
    material_name = UnicodeAttribute()
    record_type = UnicodeAttribute()  # in, out, adjustment
    quantity = NumberAttribute()
    unit_price = NumberAttribute(null=True)
    
    # For stock-in
    supplier_name = UnicodeAttribute(null=True)
    
    # For stock-out
    project_id = UnicodeAttribute(null=True)
    project_name = UnicodeAttribute(null=True)
    requester_name = UnicodeAttribute(null=True)
    purpose = UnicodeAttribute(null=True)
    
    # For adjustment (盘点)
    system_quantity = NumberAttribute(null=True)
    actual_quantity = NumberAttribute(null=True)
    adjustment_reason = UnicodeAttribute(null=True)
    
    record_date = UnicodeAttribute()
    attachments = ListAttribute(of=AttachmentMap, default=list)

    @staticmethod
    def make_pk(material_id: str) -> str:
        return f"MATERIAL#{material_id}"

    @staticmethod
    def make_sk(record_id: str) -> str:
        return f"STOCK#{record_id}"

    @staticmethod
    def make_gsi2pk(project_id: str) -> str:
        return f"PROJECT#{project_id}"
