"""Invoice router - 分批次开票，一个批次可含多张不同税率的发票。

HZY 2026-08-20: 100 万的项目甲方先要 40 万预付款发票，其中材料 30 万(13%)、
工费 10 万(9%) 是两张；剩下 60 万另一个时间开 —— 所以按「批次 + 单张发票」两层管理。
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
from pynamodb.exceptions import DoesNotExist
from typing import Optional

from ..models.contract import ContractModel
from ..models.invoice import InvoiceBatchModel, InvoiceRecordModel
from ..schemas.invoice import (
    InvoiceBatchCreate, InvoiceBatchUpdate, InvoiceRecordCreate, InvoiceRecordUpdate,
)
from ..schemas.common import APIResponse
from ..utils.attachments import to_attachment_maps, attachment_dicts
from ..utils.permissions import require_permission
from ..services.audit import log_action
from ..services import invoice_calc as calc

router = APIRouter(prefix="/api/invoices", tags=["发票管理"])

BATCH_ENTITY = "invoice_batch"
RECORD_ENTITY = "invoice_record"


def _user_name(u: dict) -> str:
    return f"{u.get('username','')}({u.get('display_name','')})"


def _generate_batch_no() -> str:
    return f"FP-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"


def _record_to_dict(r) -> dict:
    return {
        "invoice_id": r.invoice_id,
        "batch_id": r.batch_id,
        "invoice_no": r.invoice_no,
        "invoice_code": r.invoice_code,
        "category": r.category,
        "category_label": calc.CATEGORY_LABELS.get(r.category, r.category),
        "tax_rate": float(r.tax_rate or 0),
        "amount_with_tax": float(r.amount_with_tax or 0),
        "amount_without_tax": float(r.amount_without_tax or 0),
        "tax_amount": float(r.tax_amount or 0),
        "issue_date": r.issue_date,
        "buyer_name": r.buyer_name,
        "seller_name": r.seller_name,
        "contract_id": r.contract_id,
        "contract_no": r.contract_no,
        "project_id": r.project_id,
        "project_name": r.project_name,
        "remarks": r.remarks,
        "attachments": attachment_dicts(r.attachments),
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _batch_to_dict(b, invoices=None) -> dict:
    return {
        "batch_id": b.batch_id,
        "batch_no": b.batch_no,
        "batch_name": b.batch_name,
        "payment_stage": b.payment_stage,
        "payment_stage_label": calc.PAYMENT_STAGE_LABELS.get(b.payment_stage, b.payment_stage),
        "contract_id": b.contract_id,
        "contract_no": b.contract_no,
        "project_id": b.project_id,
        "project_name": b.project_name,
        "issue_date": b.issue_date,
        "planned_amount": b.planned_amount,
        "total_amount_with_tax": float(b.total_amount_with_tax or 0),
        "total_amount_without_tax": float(b.total_amount_without_tax or 0),
        "total_tax_amount": float(b.total_tax_amount or 0),
        "invoice_count": int(b.invoice_count or 0),
        "status": b.status,
        "status_label": calc.BATCH_STATUS_LABELS.get(b.status, b.status),
        "remarks": b.remarks,
        "invoices": [_record_to_dict(i) for i in (invoices or [])],
        "created_at": b.created_at,
        "updated_at": b.updated_at,
    }


def _get_batch_or_404(batch_id: str) -> InvoiceBatchModel:
    try:
        return InvoiceBatchModel.get(
            InvoiceBatchModel.make_pk(batch_id), InvoiceBatchModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="发票批次不存在")


def _batch_invoices(batch_id: str) -> list:
    """All invoices under a batch (same PK, SK prefix INVOICE#)."""
    return list(InvoiceRecordModel.query(
        InvoiceRecordModel.make_pk(batch_id),
        InvoiceRecordModel.SK.startswith("INVOICE#"),
    ))


def _refresh_batch_totals(batch: InvoiceBatchModel) -> dict:
    """Recompute the batch rollup from its invoices and persist it."""
    invoices = _batch_invoices(batch.batch_id)
    totals = calc.batch_totals([_record_to_dict(i) for i in invoices])
    batch.invoice_count = totals["invoice_count"]
    batch.total_amount_with_tax = totals["total_amount_with_tax"]
    batch.total_amount_without_tax = totals["total_amount_without_tax"]
    batch.total_tax_amount = totals["total_tax_amount"]
    batch.updated_at = datetime.now(timezone.utc).isoformat()
    batch.save()
    return {"totals": totals, "invoices": invoices}


def _resolve_record_amounts(category: str, tax_rate, amount_with_tax,
                            amount_without_tax, tax_amount) -> dict:
    rate = tax_rate if tax_rate is not None else calc.default_rate_for(category)
    try:
        return calc.resolve_amounts(amount_with_tax, rate, amount_without_tax, tax_amount)
    except calc.InvoiceAmountError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- 批次 -------------------------------------------------------------------

@router.get("/batches")
def list_batches(
    contract_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: dict = Depends(require_permission("invoice:view"))
):
    """List invoice batches with their invoices."""
    batches = list(InvoiceBatchModel.scan(filter_condition=InvoiceBatchModel.entity_type == BATCH_ENTITY))
    if contract_id:
        batches = [b for b in batches if b.contract_id == contract_id]
    if project_id:
        batches = [b for b in batches if b.project_id == project_id]
    if status:
        batches = [b for b in batches if b.status == status]

    records = list(InvoiceRecordModel.scan(filter_condition=InvoiceRecordModel.entity_type == RECORD_ENTITY))
    by_batch: dict[str, list] = {}
    for r in records:
        by_batch.setdefault(r.batch_id, []).append(r)

    data = [_batch_to_dict(b, sorted(by_batch.get(b.batch_id, []), key=lambda x: x.created_at or ""))
            for b in batches]
    data.sort(key=lambda x: (x["issue_date"] or "", x["created_at"] or ""), reverse=True)
    return APIResponse(data=data, total=len(data))


@router.get("/summary")
def invoice_summary(
    contract_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    current_user: dict = Depends(require_permission("invoice:view"))
):
    """开票进度: 合同额 / 已开票 / 未开票 + 按类别与税率汇总。作废批次不计入。"""
    if not contract_id and not project_id:
        raise HTTPException(status_code=400, detail="请指定 contract_id 或 project_id")

    batches = list(InvoiceBatchModel.scan(filter_condition=InvoiceBatchModel.entity_type == BATCH_ENTITY))
    if contract_id:
        batches = [b for b in batches if b.contract_id == contract_id]
    if project_id:
        batches = [b for b in batches if b.project_id == project_id]
    live_batch_ids = {b.batch_id for b in batches if b.status != "void"}

    records = [r for r in InvoiceRecordModel.scan(filter_condition=InvoiceRecordModel.entity_type == RECORD_ENTITY)
               if r.batch_id in live_batch_ids]

    # 基数: 指定合同用该合同金额; 指定项目用该项目所有甲方合同金额
    contracts = list(ContractModel.scan(filter_condition=ContractModel.entity_type == "contract"))
    if contract_id:
        contract_amount = sum(c.amount_with_tax or 0 for c in contracts if c.contract_id == contract_id)
    else:
        contract_amount = sum(c.amount_with_tax or 0 for c in contracts
                              if c.project_id == project_id and c.contract_type == "client")

    progress = calc.invoice_progress(contract_amount, [_record_to_dict(r) for r in records])
    progress["batch_count"] = len(live_batch_ids)
    progress["invoice_count"] = len(records)
    return APIResponse(data=progress)


@router.get("/batches/{batch_id}")
def get_batch(batch_id: str, current_user: dict = Depends(require_permission("invoice:view"))):
    """Get one batch with its invoices."""
    batch = _get_batch_or_404(batch_id)
    invoices = sorted(_batch_invoices(batch_id), key=lambda x: x.created_at or "")
    return APIResponse(data=_batch_to_dict(batch, invoices))


@router.post("/batches")
def create_batch(req: InvoiceBatchCreate, current_user: dict = Depends(require_permission("invoice:manage"))):
    """Create an invoice batch, optionally with its invoices in one call."""
    try:
        contract = ContractModel.get(
            ContractModel.make_pk(req.contract_id), ContractModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=400, detail="关联合同不存在")

    batch_id = str(uuid.uuid4())[:8]
    batch_no = _generate_batch_no()
    now = datetime.now(timezone.utc).isoformat()
    issue_date = req.issue_date or now[:10]

    b = InvoiceBatchModel()
    b.PK = InvoiceBatchModel.make_pk(batch_id)
    b.SK = InvoiceBatchModel.make_sk()
    b.GSI1PK = InvoiceBatchModel.make_gsi1pk(req.contract_id)
    b.GSI1SK = InvoiceBatchModel.make_gsi1sk(issue_date, batch_id)
    project_id = req.project_id or contract.project_id
    if project_id:
        b.GSI2PK = InvoiceBatchModel.make_gsi2pk(project_id)
        b.GSI2SK = InvoiceBatchModel.make_gsi2sk(batch_id)
    b.entity_type = BATCH_ENTITY
    b.batch_id = batch_id
    b.batch_no = batch_no
    b.batch_name = req.batch_name
    b.payment_stage = req.payment_stage
    b.contract_id = req.contract_id
    b.contract_no = req.contract_no or contract.contract_no
    b.project_id = project_id
    b.project_name = req.project_name or contract.project_name
    b.issue_date = issue_date
    b.planned_amount = req.planned_amount
    b.status = req.status
    b.remarks = req.remarks
    b.created_at = now
    b.updated_at = now
    b.created_by = current_user["user_id"]
    b.save()

    for item in (req.invoices or []):
        _save_record(b, item, current_user)
    if req.invoices:
        _refresh_batch_totals(b)

    log_action(current_user["user_id"], _user_name(current_user), "create", "invoice_batch", batch_id, f"创建发票批次: {batch_no} {req.batch_name or ''}")
    return APIResponse(message=f"发票批次 {batch_no} 创建成功",
                       data={"batch_id": batch_id, "batch_no": batch_no})


@router.put("/batches/{batch_id}")
def update_batch(batch_id: str, req: InvoiceBatchUpdate, current_user: dict = Depends(require_permission("invoice:manage"))):
    """Update batch metadata (totals stay derived from the invoices)."""
    batch = _get_batch_or_404(batch_id)
    for key, value in req.model_dump(exclude_none=True).items():
        setattr(batch, key, value)
    if req.issue_date:
        batch.GSI1SK = InvoiceBatchModel.make_gsi1sk(req.issue_date, batch_id)
    batch.updated_at = datetime.now(timezone.utc).isoformat()
    batch.updated_by = current_user["user_id"]
    batch.save()
    log_action(current_user["user_id"], _user_name(current_user), "update", "invoice_batch", batch_id, f"更新发票批次: {batch.batch_no}")
    return APIResponse(message="发票批次更新成功")


@router.delete("/batches/{batch_id}")
def delete_batch(batch_id: str, current_user: dict = Depends(require_permission("invoice:manage"))):
    """Delete a batch together with its invoices."""
    batch = _get_batch_or_404(batch_id)
    invoices = _batch_invoices(batch_id)
    for invoice in invoices:
        invoice.delete()
    log_action(current_user["user_id"], _user_name(current_user), "delete", "invoice_batch", batch_id, f"删除发票批次: {batch.batch_no}（含 {len(invoices)} 张发票）")
    batch.delete()
    return APIResponse(message="发票批次删除成功")


# --- 单张发票 ---------------------------------------------------------------

def _save_record(batch: InvoiceBatchModel, req: InvoiceRecordCreate, current_user: dict) -> str:
    """Persist one invoice under `batch`; returns the new invoice_id."""
    amounts = _resolve_record_amounts(
        req.category, req.tax_rate, req.amount_with_tax, req.amount_without_tax, req.tax_amount)

    invoice_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    issue_date = req.issue_date or batch.issue_date or now[:10]

    r = InvoiceRecordModel()
    r.PK = InvoiceRecordModel.make_pk(batch.batch_id)
    r.SK = InvoiceRecordModel.make_sk(invoice_id)
    r.GSI1PK = InvoiceRecordModel.make_gsi1pk(batch.contract_id)
    r.GSI1SK = InvoiceRecordModel.make_gsi1sk(issue_date, invoice_id)
    if batch.project_id:
        r.GSI2PK = InvoiceRecordModel.make_gsi2pk(batch.project_id)
        r.GSI2SK = InvoiceRecordModel.make_gsi2sk(invoice_id)
    r.entity_type = RECORD_ENTITY
    r.invoice_id = invoice_id
    r.batch_id = batch.batch_id
    r.invoice_no = req.invoice_no
    r.invoice_code = req.invoice_code
    r.category = req.category
    r.tax_rate = amounts["tax_rate"]
    r.amount_with_tax = amounts["amount_with_tax"]
    r.amount_without_tax = amounts["amount_without_tax"]
    r.tax_amount = amounts["tax_amount"]
    r.issue_date = issue_date
    r.buyer_name = req.buyer_name
    r.seller_name = req.seller_name
    r.contract_id = batch.contract_id
    r.contract_no = batch.contract_no
    r.project_id = batch.project_id
    r.project_name = batch.project_name
    r.remarks = req.remarks
    r.attachments = to_attachment_maps(req.attachments)
    r.created_at = now
    r.updated_at = now
    r.created_by = current_user["user_id"]
    r.save()
    return invoice_id


@router.post("/batches/{batch_id}/items")
def add_invoice(batch_id: str, req: InvoiceRecordCreate, current_user: dict = Depends(require_permission("invoice:manage"))):
    """Add one invoice to a batch."""
    batch = _get_batch_or_404(batch_id)
    invoice_id = _save_record(batch, req, current_user)
    _refresh_batch_totals(batch)
    log_action(current_user["user_id"], _user_name(current_user), "create", "invoice", invoice_id, f"新增发票: {req.invoice_no or invoice_id} ¥{req.amount_with_tax} ({calc.CATEGORY_LABELS.get(req.category, req.category)})")
    return APIResponse(message="发票添加成功", data={"invoice_id": invoice_id})


@router.put("/batches/{batch_id}/items/{invoice_id}")
def update_invoice(batch_id: str, invoice_id: str, req: InvoiceRecordUpdate, current_user: dict = Depends(require_permission("invoice:manage"))):
    """Update one invoice; amounts are re-derived when any amount field changes."""
    batch = _get_batch_or_404(batch_id)
    try:
        r = InvoiceRecordModel.get(
            InvoiceRecordModel.make_pk(batch_id), InvoiceRecordModel.make_sk(invoice_id))
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="发票不存在")

    update_data = req.model_dump(
        exclude_none=True,
        exclude={"attachments", "amount_with_tax", "amount_without_tax", "tax_amount", "tax_rate"})
    for key, value in update_data.items():
        setattr(r, key, value)

    if any(v is not None for v in (req.amount_with_tax, req.amount_without_tax, req.tax_amount, req.tax_rate)):
        amounts = _resolve_record_amounts(
            req.category or r.category,
            req.tax_rate if req.tax_rate is not None else float(r.tax_rate or 0),
            req.amount_with_tax if req.amount_with_tax is not None else float(r.amount_with_tax or 0),
            req.amount_without_tax,
            req.tax_amount)
        r.tax_rate = amounts["tax_rate"]
        r.amount_with_tax = amounts["amount_with_tax"]
        r.amount_without_tax = amounts["amount_without_tax"]
        r.tax_amount = amounts["tax_amount"]

    if req.attachments is not None:
        r.attachments = to_attachment_maps(req.attachments)
    if req.issue_date:
        r.GSI1SK = InvoiceRecordModel.make_gsi1sk(req.issue_date, invoice_id)

    r.updated_at = datetime.now(timezone.utc).isoformat()
    r.updated_by = current_user["user_id"]
    r.save()
    _refresh_batch_totals(batch)
    log_action(current_user["user_id"], _user_name(current_user), "update", "invoice", invoice_id, f"更新发票: {r.invoice_no or invoice_id}")
    return APIResponse(message="发票更新成功")


@router.delete("/batches/{batch_id}/items/{invoice_id}")
def delete_invoice(batch_id: str, invoice_id: str, current_user: dict = Depends(require_permission("invoice:manage"))):
    """Delete one invoice from a batch."""
    batch = _get_batch_or_404(batch_id)
    try:
        r = InvoiceRecordModel.get(
            InvoiceRecordModel.make_pk(batch_id), InvoiceRecordModel.make_sk(invoice_id))
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="发票不存在")
    log_action(current_user["user_id"], _user_name(current_user), "delete", "invoice", invoice_id, f"删除发票: {r.invoice_no or invoice_id}")
    r.delete()
    _refresh_batch_totals(batch)
    return APIResponse(message="发票删除成功")
