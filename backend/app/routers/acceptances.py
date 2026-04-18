"""Acceptance documents router."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
from pynamodb.exceptions import DoesNotExist
from typing import Optional

from ..models.acceptance import AcceptanceDocModel, AcceptanceMemberMap
from ..schemas.acceptance import AcceptanceCreate, AcceptanceUpdate
from ..schemas.common import APIResponse
from ..utils.auth import get_current_user, require_roles
from ..services.audit import log_action

router = APIRouter(prefix="/api/acceptances", tags=["验收资料"])

def _un(u): return f"{u.get('username','')}({u.get('display_name','')})"


def _acceptance_to_dict(a):
    def _att_list(items):
        return [{"file_id": x.file_id, "file_name": x.file_name, "file_type": x.file_type,
                 "file_size": x.file_size, "s3_key": x.s3_key, "upload_time": x.upload_time}
                for x in (items or [])]
    return {
        "acceptance_id": a.acceptance_id,
        "project_id": a.project_id,
        "project_name": a.project_name,
        "acceptance_date": a.acceptance_date,
        "acceptance_location": a.acceptance_location,
        "acceptance_team": [{"name": m.name, "title": m.title, "phone": m.phone} for m in (a.acceptance_team or [])],
        "status": a.status,
        "result": a.result,
        "rectification_requirements": a.rectification_requirements,
        "rectification_deadline": a.rectification_deadline,
        "basic_docs": _att_list(a.basic_docs),
        "engineering_docs": _att_list(a.engineering_docs),
        "compliance_docs": _att_list(a.compliance_docs),
        "result_docs": _att_list(a.result_docs),
        "other_docs": _att_list(a.other_docs),
        "rectification_docs": _att_list(a.rectification_docs),
        "created_at": a.created_at,
        "updated_at": a.updated_at,
    }


@router.get("")
def list_acceptances(
    status: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """List acceptance documents."""
    results = list(AcceptanceDocModel.scan(filter_condition=AcceptanceDocModel.entity_type == "acceptance"))
    if status:
        results = [r for r in results if r.status == status]
    if project_id:
        results = [r for r in results if r.project_id == project_id]
    data = [_acceptance_to_dict(a) for a in results]
    return APIResponse(data=data, total=len(data))


@router.get("/{acceptance_id}")
def get_acceptance(acceptance_id: str, current_user: dict = Depends(get_current_user)):
    """Get acceptance document detail."""
    try:
        a = AcceptanceDocModel.get(AcceptanceDocModel.make_pk(acceptance_id), AcceptanceDocModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="验收记录不存在")
    return APIResponse(data=_acceptance_to_dict(a))


@router.post("")
def create_acceptance(req: AcceptanceCreate, current_user: dict = Depends(require_roles("admin", "project_manager"))):
    """Create acceptance record."""
    acceptance_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    
    a = AcceptanceDocModel()
    a.PK = AcceptanceDocModel.make_pk(acceptance_id)
    a.SK = AcceptanceDocModel.make_sk()
    a.GSI1PK = AcceptanceDocModel.make_gsi1pk("pending_upload")
    a.GSI1SK = f"{now}#{acceptance_id}"
    a.GSI2PK = AcceptanceDocModel.make_gsi2pk(req.project_id)
    a.GSI2SK = f"ACCEPTANCE#{acceptance_id}"
    a.entity_type = "acceptance"
    a.acceptance_id = acceptance_id
    a.project_id = req.project_id
    a.project_name = req.project_name
    a.acceptance_date = req.acceptance_date
    a.acceptance_location = req.acceptance_location
    a.status = "pending_upload"
    a.created_at = now
    a.updated_at = now
    a.created_by = current_user["user_id"]
    
    if req.acceptance_team:
        team = []
        for m in req.acceptance_team:
            member = AcceptanceMemberMap()
            member.name = m.name
            member.title = m.title
            member.phone = m.phone
            team.append(member)
        a.acceptance_team = team
    
    a.save()
    log_action(current_user["user_id"], _un(current_user), "create", "acceptance", acceptance_id, f"创建验收: {req.project_name}")
    return APIResponse(message="验收记录创建成功", data={"acceptance_id": acceptance_id})


@router.put("/{acceptance_id}")
def update_acceptance(acceptance_id: str, req: AcceptanceUpdate, current_user: dict = Depends(require_roles("admin", "project_manager"))):
    """Update acceptance record."""
    try:
        a = AcceptanceDocModel.get(AcceptanceDocModel.make_pk(acceptance_id), AcceptanceDocModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="验收记录不存在")
    
    update_data = req.model_dump(exclude_none=True, exclude={"acceptance_team", "basic_docs", "engineering_docs"})
    for key, value in update_data.items():
        setattr(a, key, value)

    def _convert_docs(docs_list):
        from ..models.base import AttachmentMap
        result = []
        for d in docs_list:
            att = AttachmentMap()
            att.file_id = d.get("file_id", "")
            att.file_name = d.get("file_name", "")
            att.file_type = d.get("file_type", "")
            att.file_size = d.get("file_size", 0)
            att.s3_key = d.get("s3_key", "")
            att.upload_time = d.get("upload_time", "")
            att.uploaded_by = d.get("uploaded_by", "")
            result.append(att)
        return result

    if req.basic_docs is not None:
        a.basic_docs = _convert_docs(req.basic_docs)
    if req.engineering_docs is not None:
        a.engineering_docs = _convert_docs(req.engineering_docs)
    
    if req.acceptance_team is not None:
        team = []
        for m in req.acceptance_team:
            member = AcceptanceMemberMap()
            member.name = m.name
            member.title = m.title
            member.phone = m.phone
            team.append(member)
        a.acceptance_team = team
    
    if req.status:
        a.GSI1PK = AcceptanceDocModel.make_gsi1pk(req.status)
    
    a.updated_at = datetime.now(timezone.utc).isoformat()
    a.updated_by = current_user["user_id"]
    a.save()
    log_action(current_user["user_id"], _un(current_user), "update", "acceptance", acceptance_id, f"更新验收: {a.project_name}")
    return APIResponse(message="验收记录更新成功")


@router.delete("/{acceptance_id}")
def delete_acceptance(acceptance_id: str, current_user: dict = Depends(require_roles("admin"))):
    """Delete acceptance record."""
    try:
        a = AcceptanceDocModel.get(AcceptanceDocModel.make_pk(acceptance_id), AcceptanceDocModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="验收记录不存在")
    log_action(current_user["user_id"], _un(current_user), "delete", "acceptance", acceptance_id, f"删除验收: {a.project_name}")
    a.delete()
    return APIResponse(message="验收记录删除成功")
