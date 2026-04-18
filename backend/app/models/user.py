"""User model for DynamoDB single-table design.

PK: USER#{user_id}
SK: PROFILE
GSI1PK: ROLE#{role}
GSI1SK: USER#{user_id}
"""
from pynamodb.attributes import UnicodeAttribute, BooleanAttribute, NumberAttribute
from .base import BaseModel


class UserModel(BaseModel):
    """User entity.
    
    Roles: admin, finance, project_manager, procurement, construction, warehouse
    """
    # User-specific fields
    user_id = UnicodeAttribute()
    username = UnicodeAttribute()
    display_name = UnicodeAttribute()
    password_hash = UnicodeAttribute()
    role = UnicodeAttribute()  # admin, finance, project_manager, procurement, construction, warehouse
    phone = UnicodeAttribute(null=True)
    email = UnicodeAttribute(null=True)
    department = UnicodeAttribute(null=True)
    is_active = BooleanAttribute(default=True)
    login_fail_count = NumberAttribute(default=0)
    locked_until = UnicodeAttribute(null=True)

    @staticmethod
    def make_pk(user_id: str) -> str:
        return f"USER#{user_id}"

    @staticmethod
    def make_sk() -> str:
        return "PROFILE"

    @staticmethod
    def make_gsi1pk(role: str) -> str:
        return f"ROLE#{role}"

    @staticmethod
    def make_gsi1sk(user_id: str) -> str:
        return f"USER#{user_id}"
