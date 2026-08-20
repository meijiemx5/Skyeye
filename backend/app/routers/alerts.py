"""项目预警看板 + 待办中心.

HZY 2026-08-20: 「正式上线就要让他们每天第一件事就是看系统有什么事没做，
只要系统上面有待办作为通知就最好」—— 规则判定全在 services/alerts.py，
本文件只负责取数、按角色过滤、组装响应。
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional

from ..models.project import ProjectModel
from ..models.contract import ContractModel
from ..models.reimbursement import ReimbursementModel
from ..models.acceptance import AcceptanceDocModel
from ..models.inventory import MaterialModel, StockRecordModel
from ..models.invoice import InvoiceBatchModel, InvoiceRecordModel
from ..schemas.common import APIResponse
from ..utils.auth import get_current_user
from ..utils.permissions import require_permission
from ..services import alerts
from ..services.cost import project_material_cost

router = APIRouter(prefix="/api", tags=["预警与待办"])

DOC_FIELDS = ("basic_docs", "engineering_docs", "compliance_docs",
              "result_docs", "other_docs", "rectification_docs")


def _load_context() -> dict:
    """One pass over the table; the dataset is small (20-person company)."""
    projects = list(ProjectModel.scan(filter_condition=ProjectModel.entity_type == "project"))
    contracts = list(ContractModel.scan(filter_condition=ContractModel.entity_type == "contract"))
    reimbursements = list(ReimbursementModel.scan(filter_condition=ReimbursementModel.entity_type == "reimbursement"))
    acceptances = list(AcceptanceDocModel.scan(filter_condition=AcceptanceDocModel.entity_type == "acceptance"))
    materials = list(MaterialModel.scan(filter_condition=MaterialModel.entity_type == "material"))
    stock_records = list(StockRecordModel.scan(filter_condition=StockRecordModel.entity_type == "stock_record"))
    batches = list(InvoiceBatchModel.scan(filter_condition=InvoiceBatchModel.entity_type == "invoice_batch"))
    invoice_records = list(InvoiceRecordModel.scan(filter_condition=InvoiceRecordModel.entity_type == "invoice_record"))

    live_batches = {b.batch_id for b in batches if b.status != "void"}

    return {
        "projects": [
            {
                "project_id": p.project_id, "project_name": p.project_name, "status": p.status,
                "project_manager_id": p.project_manager_id,
                "project_manager_name": p.project_manager_name,
                "start_date": p.start_date, "end_date": p.end_date, "created_at": p.created_at,
                "budget_amount": p.budget_amount, "quote_amount": p.quote_amount,
            } for p in projects
        ],
        "contracts": [
            {
                "contract_id": c.contract_id, "contract_type": c.contract_type,
                "status": c.status, "amount_with_tax": c.amount_with_tax,
                "paid_amount": c.paid_amount, "project_id": c.project_id,
            } for c in contracts
        ],
        "reimbursements": [
            {
                "reimburse_id": r.reimburse_id, "project_id": r.project_id,
                "project_name": r.project_name, "status": r.status,
                "amount_with_tax": r.amount_with_tax, "applicant_id": r.applicant_id,
                "applicant_name": r.applicant_name, "description": r.description,
                "created_at": r.created_at, "updated_at": r.updated_at,
            } for r in reimbursements
        ],
        "acceptances": [
            {
                "acceptance_id": a.acceptance_id, "project_id": a.project_id,
                "project_name": a.project_name, "status": a.status, "result": a.result,
                "rectification_requirements": a.rectification_requirements,
                "rectification_deadline": a.rectification_deadline,
                **{f: list(getattr(a, f) or []) for f in DOC_FIELDS},
            } for a in acceptances
        ],
        "materials": [
            {
                "material_id": m.material_id, "material_name": m.material_name,
                "unit": m.unit, "unit_price": m.unit_price,
                "stock_quantity": m.stock_quantity, "stock_status": m.stock_status,
                "min_stock_threshold": m.min_stock_threshold,
            } for m in materials
        ],
        "stock_records": [
            {
                "record_id": s.record_id, "material_id": s.material_id,
                "record_type": s.record_type, "quantity": s.quantity,
                "unit_price": s.unit_price, "project_id": s.project_id,
            } for s in stock_records
        ],
        "invoice_records": [
            {
                "invoice_id": i.invoice_id, "batch_id": i.batch_id,
                "project_id": i.project_id, "contract_id": i.contract_id,
                "category": i.category, "tax_rate": i.tax_rate,
                "amount_with_tax": i.amount_with_tax,
            } for i in invoice_records if i.batch_id in live_batches
        ],
    }


def _visible_projects(ctx: dict, current_user: dict) -> list[dict]:
    """Project managers only get their own projects; everyone else gets all."""
    if current_user.get("role") == "project_manager":
        return [p for p in ctx["projects"] if p["project_manager_id"] == current_user["user_id"]]
    return ctx["projects"]


def _build_checklists(ctx: dict, projects: list[dict], today=None) -> list[dict]:
    material_prices = {m["material_id"]: (m["unit_price"] or 0) for m in ctx["materials"]}
    checklists = []
    for project in projects:
        pid = project["project_id"]
        project_stock = [s for s in ctx["stock_records"] if s["project_id"] == pid]
        project_contracts = [c for c in ctx["contracts"] if c["project_id"] == pid]
        project_reimburse = [r for r in ctx["reimbursements"] if r["project_id"] == pid]

        material = project_material_cost(project_stock, material_prices)
        used = (
            sum(float(c["amount_with_tax"] or 0) for c in project_contracts
                if c["contract_type"] in ("supplier", "construction"))
            + sum(float(r["amount_with_tax"] or 0) for r in project_reimburse if r["status"] == "paid")
            + material["material_cost"]
        )

        checklists.append(alerts.evaluate_project_checklist(
            project,
            contracts=project_contracts,
            acceptances=[a for a in ctx["acceptances"] if a["project_id"] == pid],
            reimbursements=project_reimburse,
            stock_records=project_stock,
            invoice_items=[i for i in ctx["invoice_records"] if i["project_id"] == pid],
            material_cost=material["material_cost"],
            used_amount=used,
            today=today,
        ))
    return checklists


@router.get("/alerts/board")
def alerts_board(
    project_status: Optional[str] = Query("active", description="按项目状态过滤，all 表示不过滤"),
    current_user: dict = Depends(require_permission("alerts:board"))
):
    """项目看板: 每个项目的 8 项完整度灯色 + 健康度。"""
    ctx = _load_context()
    projects = _visible_projects(ctx, current_user)
    if project_status and project_status != "all":
        projects = [p for p in projects if p["status"] == project_status]

    checklists = _build_checklists(ctx, projects)
    checklists.sort(key=lambda c: (c["health_score"], -c["counts"]["overdue"]))

    return APIResponse(data={
        "projects": checklists,
        "summary": {
            "project_count": len(checklists),
            "overdue_projects": len([c for c in checklists if c["counts"]["overdue"] > 0]),
            "incomplete_projects": len([c for c in checklists if c["counts"]["ok"] < c["counts"]["total"]]),
            "overdue_items": sum(c["counts"]["overdue"] for c in checklists),
            "missing_items": sum(c["counts"]["missing"] for c in checklists),
            "warning_items": sum(c["counts"]["warning"] for c in checklists),
            "average_health": round(
                sum(c["health_score"] for c in checklists) / len(checklists), 1) if checklists else 100.0,
        },
        "checklist_keys": list(alerts.CHECKLIST_KEYS),
    })


@router.get("/alerts/project/{project_id}")
def project_alerts(project_id: str, current_user: dict = Depends(require_permission("alerts:board"))):
    """单项目完整度清单明细。"""
    ctx = _load_context()
    projects = [p for p in _visible_projects(ctx, current_user) if p["project_id"] == project_id]
    if not projects:
        raise HTTPException(status_code=404, detail="项目不存在或无权查看")
    return APIResponse(data=_build_checklists(ctx, projects)[0])


def _collect_todos(ctx: dict, current_user: dict) -> list[dict]:
    """待办只包含用户点进去真能看到的记录，否则"去处理"会跳到一个空列表。"""
    projects = _visible_projects(ctx, current_user)
    checklists = _build_checklists(ctx, projects)

    reimbursements, acceptances = ctx["reimbursements"], ctx["acceptances"]
    if current_user.get("role") == "project_manager":
        own_ids = {p["project_id"] for p in projects}
        uid = current_user["user_id"]
        reimbursements = [r for r in reimbursements
                          if r["project_id"] in own_ids or r["applicant_id"] == uid]
        acceptances = [a for a in acceptances if a["project_id"] in own_ids]

    todos = (
        alerts.todos_from_checklists(checklists, current_user)
        + alerts.todos_from_reimbursements(reimbursements, current_user)
        + alerts.todos_from_acceptances(acceptances, current_user)
        + alerts.todos_from_stock(ctx["materials"], current_user)
    )
    return alerts.sort_todos(todos)


@router.get("/todos")
def my_todos(
    todo_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """我的待办 - 上班第一件事就看这里。"""
    todos = _collect_todos(_load_context(), current_user)
    summary = alerts.summarize_todos(todos)

    if todo_type:
        todos = [t for t in todos if t["type"] == todo_type]
    if severity:
        todos = [t for t in todos if t["severity"] == severity]

    return APIResponse(data={"todos": todos, "summary": summary}, total=len(todos))


@router.get("/todos/count")
def my_todo_count(current_user: dict = Depends(get_current_user)):
    """待办数量 - 顶栏红点用，响应体保持轻量。"""
    return APIResponse(data=alerts.summarize_todos(_collect_todos(_load_context(), current_user)))
