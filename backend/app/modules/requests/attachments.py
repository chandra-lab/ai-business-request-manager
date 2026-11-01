"""Secure local attachment storage for Phase 2."""

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.attachment import Attachment
from app.models.request import Request
from app.models.user import User
from app.modules.requests import authz
from app.modules.requests.service import _add_history

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_filename(name: str) -> str:
    base = Path(name).name.strip() or "upload.bin"
    cleaned = _SAFE_NAME.sub("_", base)
    return cleaned[:180]


async def save_attachment(
    db: Session,
    *,
    user: User,
    request: Request,
    upload: UploadFile,
) -> Attachment:
    authz.require_view(user, request)
    if not (authz.can_edit_as_requester(user, request) or authz.is_admin(user)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to upload")

    settings = get_settings()
    content_type = (upload.content_type or "application/octet-stream").split(";")[0].strip().lower()
    if content_type not in settings.allowed_upload_content_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Content type not allowed: {content_type}",
        )

    data = await upload.read()
    size = len(data)
    if size == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    if size > settings.upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds max size of {settings.upload_max_bytes} bytes",
        )

    upload_root = Path(settings.upload_dir).resolve()
    request_dir = upload_root / str(request.id)
    request_dir.mkdir(parents=True, exist_ok=True)

    attachment_id = uuid4()
    safe_name = _sanitize_filename(upload.filename or "upload.bin")
    stored_name = f"{attachment_id}_{safe_name}"
    dest = request_dir / stored_name
    dest.write_bytes(data)

    # Store path relative to upload root for portability
    relative = str(Path(str(request.id)) / stored_name)

    attachment = Attachment(
        id=attachment_id,
        request_id=request.id,
        uploaded_by_id=user.id,
        filename=safe_name,
        content_type=content_type,
        storage_path=relative,
        size_bytes=size,
    )
    db.add(attachment)
    _add_history(
        db,
        request=request,
        actor=user,
        action="attachment_added",
        from_status=request.status.value,
        to_status=request.status.value,
        details=f"Uploaded {safe_name} ({size} bytes)",
    )
    db.commit()
    db.refresh(attachment)
    return attachment


def absolute_path_for(attachment: Attachment) -> Path:
    settings = get_settings()
    return Path(settings.upload_dir).resolve() / attachment.storage_path
