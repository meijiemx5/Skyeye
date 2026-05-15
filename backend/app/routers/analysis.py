"""Project analysis router - aggregates data across modules for decision support."""
from fastapi import APIRouter, Depends, Query
from typing import Optional

from ..models.contract import ContractModel
from ..models.reimbursement import ReimbursementModel
from ..models.acceptance import AcceptanceDocModel
from ..models.inventory import MaterialModel, StockRecordModel
from ..models.project import ProjectModel
from ..schemas.common import APIResponse
from ..utils.auth import get_current_user, require_roles

router = APIRouter(prefix="/api/analysis", tags=["项目分析"])


@router.get("/project/{project_id}")
def project_analysis(project_id: str, current_user: dict = Depends(get_current_user)):
    """Get comprehensive project analysis."""
    # Contracts for this project
    contracts = [c for c in ContractModel.scan(filter_condition=ContractModel.entity_type == "contract") if c.project_id == project_id]
    client_contracts = [c for c in contracts if c.contract_type == "client"]
    supplier_contracts = [c for c in contracts if c.contract_type == "supplier"]
    construction_contracts = [c for c in contracts if c.contract_type == "construction"]
    
    # Reimbursements for this project
    reimbursements = [r for r in ReimbursementModel.scan(filter_condition=ReimbursementModel.entity_type == "reimbursement") if r.project_id == project_id]
    
    # Acceptance docs for this project
    acceptances = [a for a in AcceptanceDocModel.scan(filter_condition=AcceptanceDocModel.entity_type == "acceptance") if a.project_id == project_id]
    
    # Stock records for this project (count both stock-in tied to project and stock-out)
    stock_records = [r for r in StockRecordModel.scan(filter_condition=StockRecordModel.entity_type == "stock_record")
                     if r.project_id == project_id and r.record_type in ("in", "out")]
    
    # Build material price lookup for records missing unit_price
    material_prices = {}
    if stock_records:
        all_materials = list(MaterialModel.scan(filter_condition=MaterialModel.entity_type == "material"))
        material_prices = {m.material_id: (m.unit_price or 0) for m in all_materials}
    
    # Cost analysis
    client_amount = sum(c.amount_with_tax or 0 for c in client_contracts)
    supplier_cost = sum(c.amount_with_tax or 0 for c in supplier_contracts)
    construction_cost = sum(c.amount_with_tax or 0 for c in construction_contracts)
    reimbursement_cost = sum(r.amount_with_tax or 0 for r in reimbursements if r.status == "paid")
    material_cost = sum((r.quantity or 0) * (r.unit_price or material_prices.get(r.material_id, 0)) for r in stock_records)
    
    total_cost = supplier_cost + construction_cost + reimbursement_cost + material_cost
    profit = client_amount - total_cost
    profit_rate = (profit / client_amount * 100) if client_amount > 0 else 0
    
    # Payment analysis
    client_paid = sum(c.paid_amount or 0 for c in client_contracts)
    supplier_paid = sum(c.paid_amount or 0 for c in supplier_contracts)
    construction_paid = sum(c.paid_amount or 0 for c in construction_contracts)
    
    return APIResponse(data={
        "project_id": project_id,
        "revenue": {
            "client_contract_amount": client_amount,
            "client_paid_amount": client_paid,
            "client_unpaid_amount": client_amount - client_paid,
        },
        "cost": {
            "total_cost": total_cost,
            "supplier_cost": supplier_cost,
            "construction_cost": construction_cost,
            "reimbursement_cost": reimbursement_cost,
            "material_cost": material_cost,
            "cost_breakdown": {
                "supplier_pct": (supplier_cost / total_cost * 100) if total_cost > 0 else 0,
                "construction_pct": (construction_cost / total_cost * 100) if total_cost > 0 else 0,
                "reimbursement_pct": (reimbursement_cost / total_cost * 100) if total_cost > 0 else 0,
                "material_pct": (material_cost / total_cost * 100) if total_cost > 0 else 0,
            }
        },
        "profit": {
            "profit": profit,
            "profit_rate": round(profit_rate, 2),
        },
        "payment_progress": {
            "supplier_paid": supplier_paid,
            "supplier_unpaid": supplier_cost - supplier_paid,
            "construction_paid": construction_paid,
            "construction_unpaid": construction_cost - construction_paid,
        },
        "acceptance": {
            "total": len(acceptances),
            "accepted": len([a for a in acceptances if a.result == "passed"]),
            "failed": len([a for a in acceptances if a.result == "failed"]),
            "pending": len([a for a in acceptances if not a.result]),
        },
        "reimbursement_summary": {
            "total_amount": sum(r.amount_with_tax or 0 for r in reimbursements),
            "paid_amount": sum(r.amount_with_tax or 0 for r in reimbursements if r.status == "paid"),
            "pending_amount": sum(r.amount_with_tax or 0 for r in reimbursements if r.status not in ("paid", "rejected")),
            "by_type": _group_by_expense_type(reimbursements),
        },
        "contracts_count": {
            "client": len(client_contracts),
            "supplier": len(supplier_contracts),
            "construction": len(construction_contracts),
        },
    })


def _group_by_expense_type(reimbursements):
    result = {}
    for r in reimbursements:
        t = r.expense_type
        if t not in result:
            result[t] = {"count": 0, "amount": 0}
        result[t]["count"] += 1
        result[t]["amount"] += r.amount_with_tax or 0
    return result


@router.get("/overview")
def overall_analysis(current_user: dict = Depends(require_roles("admin", "finance", "project_manager"))):
    """Get overall business analysis across all projects."""
    projects = list(ProjectModel.scan(filter_condition=ProjectModel.entity_type == "project"))
    contracts = list(ContractModel.scan(filter_condition=ContractModel.entity_type == "contract"))
    reimbursements = list(ReimbursementModel.scan(filter_condition=ReimbursementModel.entity_type == "reimbursement"))
    acceptances = list(AcceptanceDocModel.scan(filter_condition=AcceptanceDocModel.entity_type == "acceptance"))
    materials = list(MaterialModel.scan(filter_condition=MaterialModel.entity_type == "material"))
    
    client_contracts = [c for c in contracts if c.contract_type == "client"]
    supplier_contracts = [c for c in contracts if c.contract_type == "supplier"]
    
    total_revenue = sum(c.amount_with_tax or 0 for c in client_contracts)
    total_supplier_cost = sum(c.amount_with_tax or 0 for c in supplier_contracts)
    total_reimbursement = sum(r.amount_with_tax or 0 for r in reimbursements if r.status == "paid")
    inventory_value = sum((m.stock_quantity or 0) * (m.unit_price or 0) for m in materials)
    
    # Load stock records for material cost
    stock_records = list(StockRecordModel.scan(filter_condition=StockRecordModel.entity_type == "stock_record"))
    stock_out_records = [r for r in stock_records if r.record_type in ("in", "out")]

    # Per-project summary
    project_summaries = []
    for p in projects:
        pid = p.project_id
        p_client = [c for c in client_contracts if c.project_id == pid]
        p_supplier = [c for c in supplier_contracts if c.project_id == pid]
        p_construction = [c for c in contracts if c.contract_type == "construction" and c.project_id == pid]
        p_reimburse = [r for r in reimbursements if r.project_id == pid and r.status == "paid"]
        p_stock_out = [r for r in stock_out_records if r.project_id == pid]

        revenue = sum(c.amount_with_tax or 0 for c in p_client)
        # Fallback to material's current price if stock record has no unit_price
        mat_prices = {m.material_id: (m.unit_price or 0) for m in materials}
        material_cost = sum((r.quantity or 0) * (r.unit_price or mat_prices.get(r.material_id, 0)) for r in p_stock_out)
        cost = (sum(c.amount_with_tax or 0 for c in p_supplier) +
                sum(c.amount_with_tax or 0 for c in p_construction) +
                sum(r.amount_with_tax or 0 for r in p_reimburse) +
                material_cost)

        project_summaries.append({
            "project_id": pid,
            "project_name": p.project_name,
            "status": p.status,
            "revenue": revenue,
            "cost": cost,
            "profit": revenue - cost,
            "profit_rate": round((revenue - cost) / revenue * 100, 2) if revenue > 0 else 0,
        })
    
    return APIResponse(data={
        "summary": {
            "total_projects": len(projects),
            "active_projects": len([p for p in projects if p.status == "active"]),
            "completed_projects": len([p for p in projects if p.status == "completed"]),
            "total_revenue": total_revenue,
            "total_cost": total_supplier_cost + total_reimbursement,
            "total_contracts": len(contracts),
            "total_reimbursements": len(reimbursements),
            "pending_reimbursements": len([r for r in reimbursements if r.status not in ("paid", "rejected")]),
            "inventory_value": inventory_value,
            "stock_warnings": len([m for m in materials if m.stock_status in ("warning", "out_of_stock")]),
        },
        "projects": project_summaries,
        "acceptance_overview": {
            "total": len(acceptances),
            "accepted": len([a for a in acceptances if a.result == "passed"]),
            "needs_rectification": len([a for a in acceptances if a.status == "needs_rectification"]),
        },
    })
