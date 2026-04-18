"""File upload router - S3 presigned URL based upload."""
import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
import boto3

from ..schemas.common import APIResponse
from ..utils.auth import get_current_user
from ..config import get_settings

router = APIRouter(prefix="/api/upload", tags=["文件上传"])

settings = get_settings()


def _get_s3_client():
    """Get S3 client."""
    session = boto3.Session(
        region_name=settings.AWS_REGION,
        profile_name=settings.AWS_PROFILE if settings.AWS_PROFILE != "default" else None
    )
    return session.client("s3")


@router.post("/presigned-url")
def get_upload_url(
    file_name: str = Query(...),
    file_type: str = Query(...),
    entity_type: str = Query(...),  # contract, reimbursement, acceptance, inventory
    entity_id: str = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Generate S3 presigned URL for file upload."""
    file_id = str(uuid.uuid4())[:8]
    ext = file_name.rsplit(".", 1)[-1] if "." in file_name else ""
    s3_key = f"{entity_type}/{entity_id}/{file_id}.{ext}" if ext else f"{entity_type}/{entity_id}/{file_id}"
    
    s3_client = _get_s3_client()
    
    presigned_url = s3_client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.S3_BUCKET_NAME,
            "Key": s3_key,
            "ContentType": file_type,
        },
        ExpiresIn=3600,  # 1 hour
    )
    
    return APIResponse(data={
        "upload_url": presigned_url,
        "file_id": file_id,
        "s3_key": s3_key,
        "file_name": file_name,
        "file_type": file_type,
    })


@router.get("/presigned-download")
def get_download_url(
    s3_key: str = Query(...),
    download: bool = Query(False),
    current_user: dict = Depends(get_current_user)
):
    """Generate S3 presigned URL for file download."""
    s3_client = _get_s3_client()
    
    # Determine content type for inline viewing
    ext = s3_key.rsplit(".", 1)[-1].lower() if "." in s3_key else ""
    content_type_map = {
        "pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "gif": "image/gif", "svg": "image/svg+xml",
        "txt": "text/plain", "html": "text/html",
    }
    params: dict = {"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key}
    file_name = s3_key.rsplit("/", 1)[-1] if "/" in s3_key else s3_key
    if download:
        params["ResponseContentDisposition"] = f"attachment; filename=\"{file_name}\""
    elif ext in content_type_map:
        params["ResponseContentType"] = content_type_map[ext]
        params["ResponseContentDisposition"] = "inline"

    presigned_url = s3_client.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=3600,
    )
    
    return APIResponse(data={"download_url": presigned_url})
