"""Contract router.

查看权限: 完整合同仅管理员与项目负责人 (`contract:view`)，项目负责人限于自己负责的项目。
财务与采购通过 `GET /api/contracts/options` 拿到精简合同选项（合同号/名称/类型/金额/已付），
用于合同付款与报销链路的项目收款确认，拿不到条款、附件等敏感内容。
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
from pynamodb.exceptions import DoesNotExist
from typing import Optional

from ..models.contract import ContractModel
from ..schemas.contract import ContractCreate, ContractUpdate
from ..schemas.common import APIResponse
from ..utils.attachments import to_attachment_maps
from ..utils.permissions import require_permission
from ..utils.scoping import own_project_ids
from ..services.audit import log_action

router = APIRouter(prefix="/api/contracts", tags=["合同管理"])


def _user_name(u: dict) -> str:
    return f"{u.get('username','')}({u.get('display_name','')})"


def _scope_to_own_projects(results, current_user: dict):
    """Project managers only see contracts under the projects they run."""
    if current_user.get("role") != "project_manager":
        return results
    own = own_project_ids(current_user["user_id"])
    return [r for r in results if r.project_id in own]


def _contract_to_dict(c):
    return {
        "contract_id": c.contract_id,
        "contract_no": c.contract_no,
        "contract_name": c.contract_name,
        "contract_type": c.contract_type,
        "party_name": c.party_name,
        "party_contact": c.party_contact,
        "party_phone": c.party_phone,
        "party_address": c.party_address,
        "project_id": c.project_id,
        "project_name": c.project_name,
        "status": c.status,
        "sign_date": c.sign_date,
        "amount_with_tax": c.amount_with_tax,
        "amount_without_tax": c.amount_without_tax,
        "invoice_amount": c.invoice_amount,
        "invoice_date": c.invoice_date,
        "paid_amount": c.paid_amount or 0,
        "work_start_date": c.work_start_date,
        "work_end_date": c.work_end_date,
        "payment_nodes": [
            {
                "node_name": n.node_name,
                "percentage": n.percentage,
                "amount": n.amount,
                "planned_date": n.planned_date,
                "actual_date": n.actual_date,
                "status": n.status,
            } for n in (c.payment_nodes or [])
        ],
        "attachments": [
            {
                "file_id": a.file_id,
                "file_name": a.file_name,
                "file_type": a.file_type,
                "file_size": a.file_size,
                "s3_key": a.s3_key,
                "upload_time": a.upload_time,
            } for a in (c.attachments or [])
        ],
        "remarks": c.remarks,
        "special_terms": c.special_terms,
        "penalty_clause": c.penalty_clause,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


def _generate_contract_no(contract_type: str) -> str:
    """Auto-generate contract number."""
    prefix_map = {"client": "JF", "supplier": "GY", "construction": "SG"}
    prefix = prefix_map.get(contract_type, "HT")
    date_str = datetime.now().strftime("%Y%m%d")
    short_id = str(uuid.uuid4())[:4].upper()
    return f"{prefix}-{date_str}-{short_id}"


@router.get("")
def list_contracts(
    contract_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_permission("contract:view"))
):
    """List contracts with filtering (admin / project manager only)."""
    results = list(ContractModel.scan(filter_condition=ContractModel.entity_type == "contract"))

    # Apply filters
    if contract_type:
        results = [r for r in results if r.contract_type == contract_type]
    if status:
        results = [r for r in results if r.status == status]
    if project_id:
        results = [r for r in results if r.project_id == project_id]
    if keyword:
        results = [r for r in results if keyword in (r.contract_name or "") or keyword in (r.party_name or "") or keyword in (r.contract_no or "")]

    results = _scope_to_own_projects(results, current_user)

    total = len(results)
    # Pagination
    start = (page - 1) * page_size
    results = results[start:start + page_size]
    
    data = [_contract_to_dict(c) for c in results]
    return APIResponse(data=data, total=total)


@router.get("/options")
def list_contract_options(
    contract_type: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    current_user: dict = Depends(require_permission("contract:options"))
):
    """精简合同选项 - 财务付款、报销收款确认用；不含条款、附件、发票明细。"""
    results = list(ContractModel.scan(filter_condition=ContractModel.entity_type == "contract"))
    if contract_type:
        results = [r for r in results if r.contract_type == contract_type]
    if project_id:
        results = [r for r in results if r.project_id == project_id]
    results = _scope_to_own_projects(results, current_user)

    data = [
        {
            "contract_id": c.contract_id,
            "contract_no": c.contract_no,
            "contract_name": c.contract_name,
            "contract_type": c.contract_type,
            "project_id": c.project_id,
            "project_name": c.project_name,
            "amount_with_tax": c.amount_with_tax,
            "paid_amount": c.paid_amount or 0,
            "status": c.status,
        }
        for c in results
    ]
    data.sort(key=lambda x: x["contract_no"] or "")
    return APIResponse(data=data, total=len(data))


@router.get("/statistics")
def contract_statistics(
    contract_type: Optional[str] = Query(None),
    current_user: dict = Depends(require_permission("contract:view"))
):
    """Get contract statistics."""
    results = list(ContractModel.scan(filter_condition=ContractModel.entity_type == "contract"))

    if contract_type:
        results = [r for r in results if r.contract_type == contract_type]
    results = _scope_to_own_projects(results, current_user)

    stats = {
        "total_count": len(results),
        "total_amount": sum(r.amount_with_tax or 0 for r in results),
        "total_paid": sum(r.paid_amount or 0 for r in results),
        "total_unpaid": sum((r.amount_with_tax or 0) - (r.paid_amount or 0) for r in results),
        "by_type": {},
        "by_status": {},
    }
    
    for r in results:
        t = r.contract_type
        if t not in stats["by_type"]:
            stats["by_type"][t] = {"count": 0, "amount": 0}
        stats["by_type"][t]["count"] += 1
        stats["by_type"][t]["amount"] += r.amount_with_tax or 0
        
        s = r.status
        if s not in stats["by_status"]:
            stats["by_status"][s] = {"count": 0, "amount": 0}
        stats["by_status"][s]["count"] += 1
        stats["by_status"][s]["amount"] += r.amount_with_tax or 0
    
    return APIResponse(data=stats)


@router.get("/{contract_id}")
def get_contract(contract_id: str, current_user: dict = Depends(require_permission("contract:view"))):
    """Get contract detail."""
    try:
        c = ContractModel.get(ContractModel.make_pk(contract_id), ContractModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="合同不存在")
    if not _scope_to_own_projects([c], current_user):
        raise HTTPException(status_code=403, detail="只能查看自己负责项目的合同")
    return APIResponse(data=_contract_to_dict(c))


@router.post("")
def create_contract(req: ContractCreate, current_user: dict = Depends(require_permission("contract:write"))):
    """Create contract."""
    contract_id = str(uuid.uuid4())[:8]
    contract_no = req.contract_no or _generate_contract_no(req.contract_type)
    now = datetime.now(timezone.utc).isoformat()
    
    from ..models.base import PaymentNodeMap
    
    c = ContractModel()
    c.PK = ContractModel.make_pk(contract_id)
    c.SK = ContractModel.make_sk()
    c.GSI1PK = ContractModel.make_gsi1pk(req.contract_type)
    c.GSI1SK = f"{req.sign_date or now}#{contract_id}"
    if req.project_id:
        c.GSI2PK = ContractModel.make_gsi2pk(req.project_id)
        c.GSI2SK = f"CONTRACT#{contract_id}"
    c.entity_type = "contract"
    c.contract_id = contract_id
    c.contract_no = contract_no
    c.contract_name = req.contract_name
    c.contract_type = req.contract_type
    c.party_name = req.party_name
    c.party_contact = req.party_contact
    c.party_phone = req.party_phone
    c.party_address = req.party_address
    c.project_id = req.project_id
    c.project_name = req.project_name
    c.status = req.status
    c.sign_date = req.sign_date
    c.amount_with_tax = req.amount_with_tax
    c.amount_without_tax = req.amount_without_tax
    c.invoice_amount = req.invoice_amount
    c.invoice_date = req.invoice_date
    c.paid_amount = 0
    c.work_start_date = req.work_start_date
    c.work_end_date = req.work_end_date
    c.remarks = req.remarks
    c.special_terms = req.special_terms
    c.penalty_clause = req.penalty_clause
    c.created_at = now
    c.updated_at = now
    c.created_by = current_user["user_id"]
    
    # Payment nodes
    if req.payment_nodes:
        nodes = []
        for n in req.payment_nodes:
            node = PaymentNodeMap()
            node.node_name = n.node_name
            node.percentage = n.percentage
            node.amount = n.amount
            node.planned_date = n.planned_date
            node.status = "pending"
            nodes.append(node)
        c.payment_nodes = nodes
    
    c.save()
    log_action(current_user["user_id"], _user_name(current_user), "create", "contract", contract_id, f"创建合同: {req.contract_name}({contract_no})")
    return APIResponse(message="合同创建成功", data={"contract_id": contract_id, "contract_no": contract_no})


@router.put("/{contract_id}")
def update_contract(contract_id: str, req: ContractUpdate, current_user: dict = Depends(require_permission("contract:write"))):
    """Update contract."""
    try:
        c = ContractModel.get(ContractModel.make_pk(contract_id), ContractModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="合同不存在")
    
    update_data = req.model_dump(exclude_none=True, exclude={"payment_nodes", "attachments"})
    for key, value in update_data.items():
        setattr(c, key, value)

    if req.attachments is not None:
        c.attachments = to_attachment_maps(req.attachments)

    if req.payment_nodes is not None:
        from ..models.base import PaymentNodeMap
        nodes = []
        for n in req.payment_nodes:
            node = PaymentNodeMap()
            node.node_name = n.node_name
            node.percentage = n.percentage
            node.amount = n.amount
            node.planned_date = n.planned_date
            node.actual_date = n.actual_date
            node.status = n.status
            nodes.append(node)
        c.payment_nodes = nodes
    
    c.updated_at = datetime.now(timezone.utc).isoformat()
    c.updated_by = current_user["user_id"]
    c.save()
    log_action(current_user["user_id"], _user_name(current_user), "update", "contract", contract_id, f"更新合同: {c.contract_name}")
    return APIResponse(message="合同更新成功")


@router.get("/{contract_id}/payments")
def list_payments(contract_id: str, current_user: dict = Depends(require_permission("contract:options"))):
    """List payment records for a contract."""
    try:
        c = ContractModel.get(ContractModel.make_pk(contract_id), ContractModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="合同不存在")
    payments = []
    for n in (c.payment_nodes or []):
        payments.append({
            "node_name": n.node_name, "percentage": n.percentage, "amount": n.amount,
            "planned_date": n.planned_date, "actual_date": n.actual_date, "status": n.status,
        })
    return APIResponse(data=payments, total=len(payments))


@router.post("/{contract_id}/payment")
def add_payment(contract_id: str, payment: dict, current_user: dict = Depends(require_permission("contract:payment"))):
    """Add a payment record to contract. Only finance/admin can do this."""
    try:
        c = ContractModel.get(ContractModel.make_pk(contract_id), ContractModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="合同不存在")
    
    amount = payment.get("amount", 0)
    method = payment.get("payment_method", "bank_transfer")
    note = payment.get("note", "")
    payment_date = payment.get("payment_date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    
    if amount <= 0:
        raise HTTPException(status_code=400, detail="付款金额必须大于0")
    
    from ..models.base import PaymentNodeMap
    node = PaymentNodeMap()
    node.node_name = f"付款-{payment_date}"
    node.percentage = 0
    node.amount = amount
    node.planned_date = payment_date
    node.actual_date = payment_date
    node.status = "paid"
    
    nodes = list(c.payment_nodes or [])
    nodes.append(node)
    c.payment_nodes = nodes
    c.paid_amount = (c.paid_amount or 0) + amount
    c.updated_at = datetime.now(timezone.utc).isoformat()
    c.updated_by = current_user["user_id"]
    c.save()
    
    log_action(current_user["user_id"], _user_name(current_user), "payment", "contract", contract_id, 
               f"合同付款: {c.contract_name} ¥{amount} ({method}) {note}")
    return APIResponse(message=f"付款 ¥{amount} 登记成功", data={"paid_amount": c.paid_amount})


@router.delete("/{contract_id}")
def delete_contract(contract_id: str, current_user: dict = Depends(require_permission("contract:delete"))):
    """Delete contract (admin only)."""
    try:
        c = ContractModel.get(ContractModel.make_pk(contract_id), ContractModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="合同不存在")
    log_action(current_user["user_id"], _user_name(current_user), "delete", "contract", contract_id, f"删除合同: {c.contract_name}({c.contract_no})")
    c.delete()
    return APIResponse(message="合同删除成功")
