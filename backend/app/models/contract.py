"""Contract model - supports 3 types: client(甲方), supplier(供应商), construction(施工人员).

PK: CONTRACT#{contract_id}
SK: META
GSI1PK: CONTRACT_TYPE#{contract_type}
GSI1SK: {sign_date}#{contract_id}
GSI2PK: PROJECT#{project_id}
GSI2SK: CONTRACT#{contract_id}
"""
from pynamodb.attributes import UnicodeAttribute, NumberAttribute, ListAttribute
from .base import BaseModel, AttachmentMap, PaymentNodeMap


class ContractModel(BaseModel):
    """Contract entity."""
    contract_id = UnicodeAttribute()
    contract_no = UnicodeAttribute()  # 合同编号
    contract_name = UnicodeAttribute()
    contract_type = UnicodeAttribute()  # client, supplier, construction
    
    # 合同主体
    party_name = UnicodeAttribute()  # 甲方/供应商/施工人员名称
    party_contact = UnicodeAttribute(null=True)
    party_phone = UnicodeAttribute(null=True)
    party_address = UnicodeAttribute(null=True)
    
    # 关联项目
    project_id = UnicodeAttribute(null=True)
    project_name = UnicodeAttribute(null=True)
    
    # 合同状态
    status = UnicodeAttribute(default="draft")  # draft, signed, fulfilled, terminated
    sign_date = UnicodeAttribute(null=True)
    
    # 金额
    amount_with_tax = NumberAttribute(null=True)
    amount_without_tax = NumberAttribute(null=True)
    paid_amount = NumberAttribute(default=0)
    
    # 工期
    work_start_date = UnicodeAttribute(null=True)
    work_end_date = UnicodeAttribute(null=True)
    
    # 付款流程
    payment_nodes = ListAttribute(of=PaymentNodeMap, default=list)
    
    # 附件
    attachments = ListAttribute(of=AttachmentMap, default=list)
    
    # 备注
    remarks = UnicodeAttribute(null=True)
    special_terms = UnicodeAttribute(null=True)
    penalty_clause = UnicodeAttribute(null=True)

    @staticmethod
    def make_pk(contract_id: str) -> str:
        return f"CONTRACT#{contract_id}"

    @staticmethod
    def make_sk() -> str:
        return "META"

    @staticmethod
    def make_gsi1pk(contract_type: str) -> str:
        return f"CONTRACT_TYPE#{contract_type}"

    @staticmethod
    def make_gsi2pk(project_id: str) -> str:
        return f"PROJECT#{project_id}"
