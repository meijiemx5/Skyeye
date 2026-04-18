"""Project model - central entity linking contracts, reimbursements, acceptance docs, inventory.

PK: PROJECT#{project_id}
SK: META
GSI1PK: PROJECT_STATUS#{status}
GSI1SK: PROJECT#{project_id}
"""
from pynamodb.attributes import UnicodeAttribute, NumberAttribute, ListAttribute
from .base import BaseModel


class ProjectModel(BaseModel):
    """Project entity."""
    project_id = UnicodeAttribute()
    project_name = UnicodeAttribute()
    project_manager_id = UnicodeAttribute(null=True)
    project_manager_name = UnicodeAttribute(null=True)
    client_name = UnicodeAttribute(null=True)
    description = UnicodeAttribute(null=True)
    status = UnicodeAttribute(default="active")  # active, completed, suspended, cancelled
    start_date = UnicodeAttribute(null=True)
    end_date = UnicodeAttribute(null=True)
    actual_end_date = UnicodeAttribute(null=True)
    address = UnicodeAttribute(null=True)

    @staticmethod
    def make_pk(project_id: str) -> str:
        return f"PROJECT#{project_id}"

    @staticmethod
    def make_sk() -> str:
        return "META"

    @staticmethod
    def make_gsi1pk(status: str) -> str:
        return f"PROJECT_STATUS#{status}"
