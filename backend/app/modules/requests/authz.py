"""Department and HR case authorization (Phase 5)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, false, or_
from sqlalchemy.orm import Session

from app.models.hr_case_access import HRCaseAccess
from app.models.request import ConfidentialityLevel, Request, RequestStatus
from app.models.user import User
from app.modules.audit.service import write_audit


def role_set(user: User) -> set[str]:
    return set(user.role_names)


def is_admin(user: User) -> bool:
    return "admin" in role_set(user)


def is_manager(user: User) -> bool:
    return "department_manager" in role_set(user)


def is_reviewer(user: User) -> bool:
    return "reviewer" in role_set(user)


def is_hr(user: User) -> bool:
    return "hr" in role_set(user)


def is_hr_case(request: Request) -> bool:
    return bool(
        request.is_hr_sensitive
        or request.confidentiality == ConfidentialityLevel.HIGHLY_CONFIDENTIAL
    )


def has_active_hr_case_access(db: Session, user_id: UUID, request_id: UUID) -> bool:
    now = datetime.now(UTC)
    row = (
        db.query(HRCaseAccess)
        .filter(
            HRCaseAccess.request_id == request_id,
            HRCaseAccess.user_id == user_id,
            HRCaseAccess.revoked_at.is_(None),
        )
        .first()
    )
    if row is None:
        return False
    # granted_at in the past is implicit; revoked_at null means active
    _ = now
    return True


def can_access_hr_content(db: Session, user: User, request: Request) -> bool:
    """HR case content (notes, sensitive internals). Admin alone is NOT enough."""
    if not is_hr_case(request):
        return True
    if is_hr(user):
        return True
    return has_active_hr_case_access(db, user.id, request.id)


def can_view_request(db: Session, user: User, request: Request) -> bool:
    """Who may open a request record.

    HR-sensitive cases: requester, HR role, or explicit HRCaseAccess only.
    Admins do **not** automatically see HR cases.
    """
    if is_hr_case(request):
        if request.requester_id == user.id:
            return True
        return can_access_hr_content(db, user, request)

    if request.requester_id == user.id:
        return True
    if is_admin(user):
        return True
    if is_manager(user) and user.department_id and request.department_id == user.department_id:
        return True
    if is_reviewer(user) and request.status == RequestStatus.PENDING_REVIEW:
        return True
    # Same-department visibility for assigned work (department-level read)
    if (
        user.department_id
        and request.department_id
        and user.department_id == request.department_id
        and request.status
        in {
            RequestStatus.PENDING_ASSIGNMENT,
            RequestStatus.ASSIGNED,
            RequestStatus.IN_PROGRESS,
            RequestStatus.RESOLVED,
        }
    ):
        return True
    return False


def require_view(
    db: Session,
    user: User,
    request: Request,
    *,
    ip_address: str | None = None,
) -> None:
    if can_view_request(db, user, request):
        return
    write_audit(
        db,
        actor_id=user.id,
        action="authz.deny_view",
        resource_type="request",
        resource_id=str(request.id),
        details="Denied request view",
        ip_address=ip_address,
        metadata={
            "is_hr_case": is_hr_case(request),
            "roles": sorted(role_set(user)),
        },
        commit=True,
    )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")


def require_hr_content(
    db: Session,
    user: User,
    request: Request,
    *,
    ip_address: str | None = None,
) -> None:
    """Require HR role or case grant. Call after require_view when needed."""
    if can_access_hr_content(db, user, request):
        write_audit(
            db,
            actor_id=user.id,
            action="authz.hr_content_allow",
            resource_type="request",
            resource_id=str(request.id),
            details="Allowed HR case content access",
            ip_address=ip_address,
            commit=True,
        )
        return
    write_audit(
        db,
        actor_id=user.id,
        action="authz.hr_content_deny",
        resource_type="request",
        resource_id=str(request.id),
        details="Denied HR case content access",
        ip_address=ip_address,
        metadata={"roles": sorted(role_set(user))},
        commit=True,
    )
    # Requester can see the request but not notes → 403; others already 404'd on view
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="HR case content access denied",
    )


def can_edit_as_requester(user: User, request: Request) -> bool:
    return request.requester_id == user.id


def can_download_attachment(db: Session, user: User, request: Request) -> bool:
    if not can_view_request(db, user, request):
        return False
    if not is_hr_case(request):
        return True
    # HR case attachments: requester (own uploads) or HR content principals
    if request.requester_id == user.id:
        return True
    return can_access_hr_content(db, user, request)


def require_attachment_download(
    db: Session,
    user: User,
    request: Request,
    *,
    ip_address: str | None = None,
) -> None:
    if can_download_attachment(db, user, request):
        return
    write_audit(
        db,
        actor_id=user.id,
        action="authz.deny_attachment",
        resource_type="request",
        resource_id=str(request.id),
        details="Denied attachment download",
        ip_address=ip_address,
        commit=True,
    )
    if can_view_request(db, user, request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Attachment access denied")
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")


def apply_list_scope(query: Any, user: User, db: Session) -> Any:
    """Restrict list queries by role and HR boundary."""
    if is_admin(user) and not is_hr(user):
        # Admin sees non-HR cases only (unless also HR or granted — grants are per-case)
        granted_ids = [
            r.request_id
            for r in db.query(HRCaseAccess)
            .filter(HRCaseAccess.user_id == user.id, HRCaseAccess.revoked_at.is_(None))
            .all()
        ]
        return query.filter(
            or_(
                and_(
                    Request.is_hr_sensitive.is_(False),
                    Request.confidentiality == ConfidentialityLevel.STANDARD,
                ),
                Request.requester_id == user.id,
                Request.id.in_(granted_ids) if granted_ids else false(),
            )
        )

    roles = role_set(user)
    clauses = [Request.requester_id == user.id]

    if "department_manager" in roles and user.department_id is not None:
        clauses.append(
            and_(
                Request.department_id == user.department_id,
                Request.is_hr_sensitive.is_(False),
                Request.confidentiality == ConfidentialityLevel.STANDARD,
            )
        )

    if "reviewer" in roles:
        clauses.append(
            and_(
                Request.status == RequestStatus.PENDING_REVIEW,
                Request.is_hr_sensitive.is_(False),
                Request.confidentiality == ConfidentialityLevel.STANDARD,
            )
        )

    if "hr" in roles:
        clauses.append(
            or_(
                Request.is_hr_sensitive.is_(True),
                Request.confidentiality == ConfidentialityLevel.HIGHLY_CONFIDENTIAL,
            )
        )

    # Explicit case grants
    granted = (
        db.query(HRCaseAccess.request_id)
        .filter(HRCaseAccess.user_id == user.id, HRCaseAccess.revoked_at.is_(None))
        .all()
    )
    granted_ids = [g[0] for g in granted]
    if granted_ids:
        clauses.append(Request.id.in_(granted_ids))

    if is_admin(user) and is_hr(user):
        # HR+admin: union of admin non-HR and HR cases — hr clause already covers sensitive
        clauses.append(
            and_(
                Request.is_hr_sensitive.is_(False),
                Request.confidentiality == ConfidentialityLevel.STANDARD,
            )
        )

    return query.filter(or_(*clauses))
