"""Acceptance document model - project acceptance workflow and document management.

PK: ACCEPTANCE#{acceptance_id}
SK: META
GSI1PK: ACCEPTANCE_STATUS#{status}
GSI1SK: {created_at}#{acceptance_id}
GSI2PK: PROJECT#{project_id}
GSI2SK: ACCEPTANCE#{acceptance_id}
"""
from pynamodb.attributes import UnicodeAttribute, ListAttribute, MapAttribute
from .base import BaseModel, AttachmentMap


class AcceptanceMemberMap(MapAttribute):
    """Acceptance team member."""
    name = UnicodeAttribute()
    title = UnicodeAttribute(null=True)
    phone = UnicodeAttribute(null=True)


class AcceptanceDocModel(BaseModel):
    """Acceptance document entity."""
    acceptance_id = UnicodeAttribute()
    
    # 关联项目
    project_id = UnicodeAttribute()
    project_name = UnicodeAttribute()
    
    # 验收基本信息
    acceptance_date = UnicodeAttribute(null=True)
    acceptance_location = UnicodeAttribute(null=True)
    acceptance_team = ListAttribute(of=AcceptanceMemberMap, default=list)
    
    # 状态: pending_upload, uploaded, pending_acceptance, accepted, needs_rectification
    status = UnicodeAttribute(default="pending_upload")
    
    # 验收结果
    result = UnicodeAttribute(null=True)  # passed, failed
    rectification_requirements = UnicodeAttribute(null=True)
    rectification_deadline = UnicodeAttribute(null=True)
    
    # 各类资料 - 按分类存放
    basic_docs = ListAttribute(of=AttachmentMap, default=list)  # 基础验收资料
    engineering_docs = ListAttribute(of=AttachmentMap, default=list)  # 工程类资料
    compliance_docs = ListAttribute(of=AttachmentMap, default=list)  # 合规类资料
    result_docs = ListAttribute(of=AttachmentMap, default=list)  # 验收结果资料
    other_docs = ListAttribute(of=AttachmentMap, default=list)  # 其他资料
    rectification_docs = ListAttribute(of=AttachmentMap, default=list)  # 整改反馈资料

    @staticmethod
    def make_pk(acceptance_id: str) -> str:
        return f"ACCEPTANCE#{acceptance_id}"

    @staticmethod
    def make_sk() -> str:
        return "META"

    @staticmethod
    def make_gsi1pk(status: str) -> str:
        return f"ACCEPTANCE_STATUS#{status}"

    @staticmethod
    def make_gsi2pk(project_id: str) -> str:
        return f"PROJECT#{project_id}"
