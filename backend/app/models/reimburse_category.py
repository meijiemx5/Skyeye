"""Reimbursement category model - two-level hierarchy.

PK: REIMBURSE_CAT#{category_id}
SK: META
GSI1PK: REIMBURSE_CAT_PARENT#{parent_id|ROOT}
GSI1SK: SORT#{sort_order:04d}#{category_id}
"""
from pynamodb.attributes import UnicodeAttribute, NumberAttribute, BooleanAttribute
from .base import BaseModel


class ReimburseCategoryModel(BaseModel):
    """Reimbursement category entity (max two levels)."""
    category_id = UnicodeAttribute()
    name = UnicodeAttribute()
    parent_id = UnicodeAttribute(null=True)  # None or empty for level-1 (root)
    level = NumberAttribute(default=1)  # 1=parent, 2=child
    sort_order = NumberAttribute(default=0)
    is_active = BooleanAttribute(default=True)
    code = UnicodeAttribute(null=True)

    @staticmethod
    def make_pk(category_id: str) -> str:
        return f"REIMBURSE_CAT#{category_id}"

    @staticmethod
    def make_sk() -> str:
        return "META"

    @staticmethod
    def make_gsi1pk(parent_id: str = None) -> str:
        return f"REIMBURSE_CAT_PARENT#{parent_id or 'ROOT'}"

    @staticmethod
    def make_gsi1sk(sort_order: int, category_id: str) -> str:
        return f"SORT#{int(sort_order or 0):04d}#{category_id}"
