"""HR case notes and explicit case access grants (Phase 5)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.hr_case_access import HRCaseAccess
from app.models.hr_case_note import HRCaseNote
from app.models.request import Request
from app.models.user import User
from app.modules.audit.service import write_audit
from app.modules.requests import authz


def list_notes(db: Session, *, user: User, request: Request) -> list[HRCaseNote]:
    authz.require_view(db, user, request)
    authz.require_hr_content(db, user, request)
    return (
        db.query(HRCaseNote)
        .filter(HRCaseNote.request_id == request.id)
        .order_by(HRCaseNote.created_at.asc())
        .all()
    )


def add_note(
    db: Session,
    *,
    user: User,
    request: Request,
    content: str,
) -> HRCaseNote:
    if not authz.is_hr_case(request):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HR notes only allowed on HR-sensitive cases",
        )
    authz.require_view(db, user, request)
    authz.require_hr_content(db, user, request)
    if not (authz.is_hr(user) or authz.has_active_hr_case_access(db, user.id, request.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HR role or grant required")

    note = HRCaseNote(request_id=request.id, author_id=user.id, content=content.strip())
    db.add(note)
    write_audit(
        db,
        actor_id=user.id,
        action="hr.note_create",
        resource_type="request",
        resource_id=str(request.id),
        details="Created HR case note",
        metadata={"note_length": len(content.strip())},
    )
    db.commit()
    db.refresh(note)
    return note


def grant_access(
    db: Session,
    *,
    granter: User,
    request: Request,
    grantee_id: UUID,
) -> HRCaseAccess:
    if not authz.is_hr_case(request):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Access grants only apply to HR-sensitive cases",
        )
    if not authz.is_hr(granter):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HR role required to grant")

    grantee = db.query(User).filter(User.id == grantee_id, User.is_active.is_(True)).first()
    if grantee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = (
        db.query(HRCaseAccess)
        .filter(HRCaseAccess.request_id == request.id, HRCaseAccess.user_id == grantee_id)
        .first()
    )
    if existing and existing.revoked_at is None:
        return existing
    if existing:
        existing.revoked_at = None
        existing.granted_by_id = granter.id
        existing.granted_at = datetime.now(UTC)
        access = existing
    else:
        access = HRCaseAccess(
            request_id=request.id,
            user_id=grantee_id,
            granted_by_id=granter.id,
        )
        db.add(access)

    write_audit(
        db,
        actor_id=granter.id,
        action="hr.access_grant",
        resource_type="request",
        resource_id=str(request.id),
        details=f"Granted HR case access to {grantee.email}",
        metadata={"grantee_id": str(grantee_id)},
    )
    db.commit()
    db.refresh(access)
    return access


def list_access(db: Session, *, user: User, request: Request) -> list[HRCaseAccess]:
    authz.require_view(db, user, request)
    authz.require_hr_content(db, user, request)
    return (
        db.query(HRCaseAccess)
        .filter(HRCaseAccess.request_id == request.id, HRCaseAccess.revoked_at.is_(None))
        .order_by(HRCaseAccess.granted_at.desc())
        .all()
    )


def revoke_access(
    db: Session,
    *,
    actor: User,
    request: Request,
    access_id: UUID,
) -> HRCaseAccess:
    if not authz.is_hr(actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HR role required")
    access = (
        db.query(HRCaseAccess)
        .filter(HRCaseAccess.id == access_id, HRCaseAccess.request_id == request.id)
        .first()
    )
    if access is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found")
    access.revoked_at = datetime.now(UTC)
    write_audit(
        db,
        actor_id=actor.id,
        action="hr.access_revoke",
        resource_type="request",
        resource_id=str(request.id),
        details=f"Revoked HR case access for user {access.user_id}",
        metadata={"access_id": str(access_id), "user_id": str(access.user_id)},
    )
    db.commit()
    db.refresh(access)
    return access
