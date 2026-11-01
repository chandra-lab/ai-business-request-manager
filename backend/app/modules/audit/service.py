"""Audit log helpers for security-sensitive events."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def write_audit(
    db: Session,
    *,
    actor_id: UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    details: str | None = None,
    ip_address: str | None = None,
    metadata: dict[str, Any] | None = None,
    commit: bool = False,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        metadata_json=metadata,
    )
    db.add(entry)
    if commit:
        db.commit()
    else:
        db.flush()
    return entry
