"""Invoice models - batched invoicing with per-invoice tax rates.

发票不是一次性开具: 一个合同分多个批次开票, 一个批次内可能有多张不同税率的发票
(材料 13% / 施工 9% / 技术服务 6%)。所以批次与单张发票分两层建模。

InvoiceBatch:  PK: INVOICE_BATCH#{batch_id}, SK: META
InvoiceRecord: PK: INVOICE_BATCH#{batch_id}, SK: INVOICE#{invoice_id}
GSI1PK: INVOICE_CONTRACT#{contract_id}
GSI2PK: PROJECT#{project_id}

批次与其发票共用 PK, 一次 Query 即可取出整批 (与 Material/StockRecord 同一套做法)。
"""
from pynamodb.attributes import UnicodeAttribute, NumberAttribute, ListAttribute
from .base import BaseModel, AttachmentMap


class InvoiceBatchModel(BaseModel):
    """开票批次 - 一次开票行为 (如"预付款40万")。"""
    batch_id = UnicodeAttribute()
    batch_no = UnicodeAttribute()  # FP-YYYYMMDD-XXXX
    batch_name = UnicodeAttribute(null=True)
    payment_stage = UnicodeAttribute(default="other")  # advance, progress, final, other

    contract_id = UnicodeAttribute(null=True)
    contract_no = UnicodeAttribute(null=True)
    project_id = UnicodeAttribute(null=True)
    project_name = UnicodeAttribute(null=True)

    issue_date = UnicodeAttribute(null=True)
    planned_amount = NumberAttribute(null=True)  # 本批次计划开票额

    # 由明细汇总, 每次明细变化后重算
    total_amount_with_tax = NumberAttribute(default=0)
    total_amount_without_tax = NumberAttribute(default=0)
    total_tax_amount = NumberAttribute(default=0)
    invoice_count = NumberAttribute(default=0)

    status = UnicodeAttribute(default="draft")  # draft, issued, received, void
    remarks = UnicodeAttribute(null=True)

    @staticmethod
    def make_pk(batch_id: str) -> str:
        return f"INVOICE_BATCH#{batch_id}"

    @staticmethod
    def make_sk() -> str:
        return "META"

    @staticmethod
    def make_gsi1pk(contract_id: str) -> str:
        return f"INVOICE_CONTRACT#{contract_id}"

    @staticmethod
    def make_gsi1sk(issue_date: str, batch_id: str) -> str:
        return f"BATCH#{issue_date or ''}#{batch_id}"

    @staticmethod
    def make_gsi2pk(project_id: str) -> str:
        return f"PROJECT#{project_id}"

    @staticmethod
    def make_gsi2sk(batch_id: str) -> str:
        return f"INVOICE_BATCH#{batch_id}"


class InvoiceRecordModel(BaseModel):
    """单张发票 - 税率随类别不同, 附件挂在这一层。"""
    invoice_id = UnicodeAttribute()
    batch_id = UnicodeAttribute()

    invoice_no = UnicodeAttribute(null=True)    # 发票号码
    invoice_code = UnicodeAttribute(null=True)  # 发票代码
    category = UnicodeAttribute(default="other")  # material, construction, service, other
    tax_rate = NumberAttribute(default=0)  # 小数存储: 13% -> 0.13

    amount_with_tax = NumberAttribute()
    amount_without_tax = NumberAttribute(null=True)
    tax_amount = NumberAttribute(null=True)

    issue_date = UnicodeAttribute(null=True)
    buyer_name = UnicodeAttribute(null=True)
    seller_name = UnicodeAttribute(null=True)

    contract_id = UnicodeAttribute(null=True)
    contract_no = UnicodeAttribute(null=True)
    project_id = UnicodeAttribute(null=True)
    project_name = UnicodeAttribute(null=True)

    remarks = UnicodeAttribute(null=True)
    attachments = ListAttribute(of=AttachmentMap, default=list)

    @staticmethod
    def make_pk(batch_id: str) -> str:
        return f"INVOICE_BATCH#{batch_id}"

    @staticmethod
    def make_sk(invoice_id: str) -> str:
        return f"INVOICE#{invoice_id}"

    @staticmethod
    def make_gsi1pk(contract_id: str) -> str:
        return f"INVOICE_CONTRACT#{contract_id}"

    @staticmethod
    def make_gsi1sk(issue_date: str, invoice_id: str) -> str:
        return f"INVOICE#{issue_date or ''}#{invoice_id}"

    @staticmethod
    def make_gsi2pk(project_id: str) -> str:
        return f"PROJECT#{project_id}"

    @staticmethod
    def make_gsi2sk(invoice_id: str) -> str:
        return f"INVOICE#{invoice_id}"
