"""Reimbursement model - supports full workflow: apply -> review -> payment.

PK: REIMBURSE#{reimburse_id}
SK: META
GSI1PK: REIMBURSE_STATUS#{status}
GSI1SK: {created_at}#{reimburse_id}
GSI2PK: PROJECT#{project_id}
GSI2SK: REIMBURSE#{reimburse_id}
"""
from pynamodb.attributes import (
    UnicodeAttribute, NumberAttribute, ListAttribute, MapAttribute, BooleanAttribute,
)
from .base import BaseModel, AttachmentMap


class AuditLogMap(MapAttribute):
    """Audit log entry for reimbursement review."""
    auditor_id = UnicodeAttribute()
    auditor_name = UnicodeAttribute()
    audit_time = UnicodeAttribute()
    action = UnicodeAttribute()  # approved, rejected
    comments = UnicodeAttribute(null=True)
    audit_level = UnicodeAttribute()  # manager, finance


class ReimbursementModel(BaseModel):
    """Reimbursement entity."""
    reimburse_id = UnicodeAttribute()
    
    # 报销人
    applicant_id = UnicodeAttribute()
    applicant_name = UnicodeAttribute()
    
    # 关联项目
    project_id = UnicodeAttribute(null=True)
    project_name = UnicodeAttribute(null=True)
    
    # 报销信息
    amount_with_tax = NumberAttribute()
    amount_without_tax = NumberAttribute(null=True)
    expense_type = UnicodeAttribute()  # category_id (sub if available, else parent); legacy values: material/travel/equipment_rental/other
    expense_category_id = UnicodeAttribute(null=True)  # parent category id
    expense_subcategory_id = UnicodeAttribute(null=True)  # child category id (nullable when no sub)
    description = UnicodeAttribute()  # 报销事由
    expense_date = UnicodeAttribute()  # 发生日期
    
    # 状态流转 (services/reimburse_flow.py 是唯一权威):
    # pending_review -> manager_approved -> receipt_confirmed -> document_created
    #   -> finance_approved -> voucher_generated -> paid / rejected
    status = UnicodeAttribute(default="pending_review")

    # 审核记录
    audit_logs = ListAttribute(of=AuditLogMap, default=list)

    # 项目收款确认 (硬门禁: 未确认收款不能创建单据; admin 可跳过并留痕)
    receipt_contract_id = UnicodeAttribute(null=True)
    receipt_contract_no = UnicodeAttribute(null=True)
    receipt_amount = NumberAttribute(null=True)
    receipt_date = UnicodeAttribute(null=True)
    receipt_note = UnicodeAttribute(null=True)
    receipt_confirmed_at = UnicodeAttribute(null=True)
    receipt_confirmed_by = UnicodeAttribute(null=True)
    receipt_confirmed_by_name = UnicodeAttribute(null=True)
    receipt_skipped = BooleanAttribute(null=True)
    receipt_skip_reason = UnicodeAttribute(null=True)

    # 报销单据
    document_no = UnicodeAttribute(null=True)
    document_created_at = UnicodeAttribute(null=True)
    document_created_by = UnicodeAttribute(null=True)
    document_created_by_name = UnicodeAttribute(null=True)

    # 会计凭证
    voucher_no = UnicodeAttribute(null=True)
    voucher_generated_at = UnicodeAttribute(null=True)
    voucher_generated_by = UnicodeAttribute(null=True)
    voucher_generated_by_name = UnicodeAttribute(null=True)
    voucher_files = ListAttribute(of=AttachmentMap, default=list)
    
    # 当前审核人
    current_reviewer_id = UnicodeAttribute(null=True)
    current_reviewer_name = UnicodeAttribute(null=True)
    
    # 付款信息
    payment_amount = NumberAttribute(null=True)
    payment_method = UnicodeAttribute(null=True)  # bank_transfer, cash
    payment_time = UnicodeAttribute(null=True)
    payment_status = UnicodeAttribute(null=True)  # pending, paid, failed
    payment_failure_reason = UnicodeAttribute(null=True)
    
    # 凭证/回单
    vouchers = ListAttribute(of=AttachmentMap, default=list)
    payment_receipt = ListAttribute(of=AttachmentMap, default=list)

    @staticmethod
    def make_pk(reimburse_id: str) -> str:
        return f"REIMBURSE#{reimburse_id}"

    @staticmethod
    def make_sk() -> str:
        return "META"

    @staticmethod
    def make_gsi1pk(status: str) -> str:
        return f"REIMBURSE_STATUS#{status}"

    @staticmethod
    def make_gsi2pk(project_id: str) -> str:
        return f"PROJECT#{project_id}"
