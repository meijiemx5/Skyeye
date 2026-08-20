"""Attachment (de)serialization between request dicts and AttachmentMap."""
from ..models.base import AttachmentMap


def to_attachment_maps(items) -> list[AttachmentMap]:
    """Request dicts -> AttachmentMap list, ready to assign to a ListAttribute."""
    result = []
    for item in items or []:
        att = AttachmentMap()
        att.file_id = item.get("file_id", "")
        att.file_name = item.get("file_name", "")
        att.file_type = item.get("file_type", "")
        att.file_size = item.get("file_size", 0)
        att.s3_key = item.get("s3_key", "")
        att.upload_time = item.get("upload_time", "")
        att.uploaded_by = item.get("uploaded_by", "")
        result.append(att)
    return result


def attachment_dicts(items) -> list[dict]:
    """AttachmentMap list -> JSON-serializable dicts."""
    return [
        {
            "file_id": a.file_id,
            "file_name": a.file_name,
            "file_type": a.file_type,
            "file_size": a.file_size,
            "s3_key": a.s3_key,
            "upload_time": a.upload_time,
            "uploaded_by": getattr(a, "uploaded_by", None),
        }
        for a in (items or [])
    ]
