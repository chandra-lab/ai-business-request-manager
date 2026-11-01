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


# Seeded / product HR team codes — tickets here are HR-protected even if flags lag.
HR_DEPARTMENT_CODES = frozenset({"HR"})


def is_hr_case(request: Request) -> bool:
    return bool(
        request.is_hr_sensitive
        or request.confidentiality == ConfidentialityLevel.HIGHLY_CONFIDENTIAL
    )


def hr_department_ids(db: Session) -> list[UUID]:
    from app.models.department import Department

    rows = (
        db.query(Department.id)
        .filter(Department.code.in_(list(HR_DEPARTMENT_CODES)))
        .all()
    )
    return [r[0] for r in rows]


def is_hr_department_request(db: Session, request: Request) -> bool:
    if request.department_id is None:
        return False
    return request.department_id in set(hr_department_ids(db))


def is_hr_protected(db: Session, request: Request) -> bool:
    """Sensitive / highly confidential / Human Resources department tickets."""
    return is_hr_case(request) or is_hr_department_request(db, request)


def non_hr_team_predicate():
    """SQLAlchemy filter: exclude sensitive + highly confidential (dept filter separate)."""
    return and_(
        Request.is_hr_sensitive.is_(False),
        Request.confidentiality == ConfidentialityLevel.STANDARD,
    )


def apply_exclude_hr_protected(query: Any, db: Session) -> Any:
    """Drop HR-protected tickets from non-HR team queues / dashboards."""
    hr_ids = hr_department_ids(db)
    query = query.filter(non_hr_team_predicate())
    if hr_ids:
        query = query.filter(
            or_(Request.department_id.is_(None), Request.department_id.notin_(hr_ids))
        )
    return query


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
    """Internal HR notes / grants. Admin alone is NOT enough; reviewers are not enough."""
    if not is_hr_protected(db, request):
        return True
    if is_hr(user):
        return True
    return has_active_hr_case_access(db, user.id, request.id)


def can_read_hr_case_body(db: Session, user: User, request: Request) -> bool:
    """Full description / sensitive body for HR-protected cases.

    Allowed: the requester (own submission), HR role, reviewer, or explicit grant.
    Non-HR managers/members and other employees never receive the body — they are
    denied by ``can_view_request`` (404) or get a redacted placeholder if they
    somehow reach serialization.
    """
    if not is_hr_protected(db, request):
        return True
    if request.requester_id == user.id:
        return True
    if is_hr(user) or is_reviewer(user):
        return True
    return has_active_hr_case_access(db, user.id, request.id)


HR_BODY_REDACTION = (
    "[Redacted] Confidential HR case content is only visible to HR and reviewers."
)


def redact_description_if_needed(db: Session, user: User, request: Request) -> tuple[str, bool]:
    """Return (description, was_redacted) for API serialization."""
    if can_read_hr_case_body(db, user, request):
        return request.description, False
    return HR_BODY_REDACTION, True


def is_same_department(user: User, request: Request) -> bool:
    return bool(
        user.department_id
        and request.department_id
        and user.department_id == request.department_id
    )


_DEPT_VISIBLE_STATUSES = {
    RequestStatus.PENDING_ASSIGNMENT,
    RequestStatus.ASSIGNED,
    RequestStatus.IN_PROGRESS,
    RequestStatus.RESOLVED,
}


def can_view_request(db: Session, user: User, request: Request) -> bool:
    """Who may open a request record.

    HR-protected cases (sensitive / highly confidential / HR department):
    requester (own summary), HR role, reviewer, or explicit HRCaseAccess.
    Admins and non-HR dept members do **not** automatically see HR cases.
    Department members see non-HR tickets for their dept once routed.
    """
    if is_hr_protected(db, request):
        if request.requester_id == user.id:
            return True
        if is_hr(user) or is_reviewer(user):
            return True
        return has_active_hr_case_access(db, user.id, request.id)

    if request.requester_id == user.id:
        return True
    if is_admin(user):
        return True
    if is_manager(user) and is_same_department(user, request):
        return True
    if is_reviewer(user):
        # Review queue items, plus department-routed work reviewers may reassign
        if request.status == RequestStatus.PENDING_REVIEW:
            return True
        if request.department_id and request.status in {
            RequestStatus.PENDING_ASSIGNMENT,
            RequestStatus.ASSIGNED,
            RequestStatus.IN_PROGRESS,
        }:
            return True
    # Active assignee can always open the ticket
    from app.models.assignment import Assignment, AssignmentStatus

    active = (
        db.query(Assignment)
        .filter(
            Assignment.request_id == request.id,
            Assignment.status == AssignmentStatus.ACTIVE,
            Assignment.assignee_id == user.id,
        )
        .first()
    )
    if active is not None:
        return True
    # Same-department visibility for department members (not only managers)
    if is_same_department(user, request) and request.status in _DEPT_VISIBLE_STATUSES:
        return True
    return False


def can_view_internal_history(db: Session, user: User, request: Request | None = None) -> bool:
    """Staff roles see RequestHistory; department members use comments + status actions."""
    _ = db, request  # request reserved for future scoped rules
    return bool(is_admin(user) or is_manager(user) or is_reviewer(user) or is_hr(user))


def can_work_request(db: Session, user: User, request: Request) -> bool:
    """Progress status / work the ticket: assignee, dept member, manager, or admin."""
    if is_hr_protected(db, request):
        return can_access_hr_content(db, user, request) and is_hr(user)
    if is_admin(user):
        return True
    if is_manager(user) and is_same_department(user, request):
        return True
    if is_same_department(user, request) and request.status in _DEPT_VISIBLE_STATUSES:
        return True
    from app.models.assignment import Assignment, AssignmentStatus

    active = (
        db.query(Assignment)
        .filter(
            Assignment.request_id == request.id,
            Assignment.status == AssignmentStatus.ACTIVE,
            Assignment.assignee_id == user.id,
        )
        .first()
    )
    return active is not None


def can_assign_individual(db: Session, user: User, request: Request) -> bool:
    """Managers of the request dept, reviewers (after dept set), or admins."""
    if is_hr_protected(db, request):
        return can_access_hr_content(db, user, request) and is_hr(user)
    if is_admin(user):
        return True
    if (
        is_manager(user)
        and user.department_id
        and request.department_id
        and user.department_id == request.department_id
    ):
        return True
    if is_reviewer(user) and request.department_id is not None:
        return True
    return False


def can_set_priority(db: Session, user: User, request: Request) -> bool:
    """Reviewer, admin, or department manager (of the ticket's dept) may set priority.

    Employees view priority read-only. Managers need a department match when the
    ticket already has a department; reviewers/admins may set it earlier (e.g.
    during pending_review).
    """
    if is_hr_protected(db, request):
        return can_read_hr_case_body(db, user, request) and (
            is_hr(user) or is_reviewer(user) or has_active_hr_case_access(db, user.id, request.id)
        )
    if is_admin(user) or is_reviewer(user):
        return True
    if (
        is_manager(user)
        and user.department_id
        and request.department_id
        and user.department_id == request.department_id
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
            "is_hr_case": is_hr_protected(db, request),
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
    """Require HR role or case grant for notes. Call after require_view when needed."""
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
    # Requester/reviewer can open the ticket but not notes → 403; others already 404'd on view
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="HR case content access denied",
    )


def can_edit_as_requester(user: User, request: Request) -> bool:
    return request.requester_id == user.id


def can_download_attachment(db: Session, user: User, request: Request) -> bool:
    if not can_view_request(db, user, request):
        return False
    if not is_hr_protected(db, request):
        return True
    # HR case attachments: requester (own uploads) or HR body principals
    if request.requester_id == user.id:
        return True
    return can_read_hr_case_body(db, user, request)


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
    hr_ids = hr_department_ids(db)
    not_hr_dept = (
        or_(Request.department_id.is_(None), Request.department_id.notin_(hr_ids))
        if hr_ids
        else true_clause()
    )

    if is_admin(user) and not is_hr(user):
        # Admin sees non-HR-protected cases only (unless also HR or granted)
        granted_ids = [
            r.request_id
            for r in db.query(HRCaseAccess)
            .filter(HRCaseAccess.user_id == user.id, HRCaseAccess.revoked_at.is_(None))
            .all()
        ]
        return query.filter(
            or_(
                and_(non_hr_team_predicate(), not_hr_dept),
                Request.requester_id == user.id,
                Request.id.in_(granted_ids) if granted_ids else false(),
            )
        )

    roles = role_set(user)
    clauses = [Request.requester_id == user.id]

    if user.department_id is not None and "hr" not in roles:
        # Non-HR managers/members: never list HR-protected / HR-department tickets
        if "department_manager" in roles:
            clauses.append(
                and_(
                    Request.department_id == user.department_id,
                    non_hr_team_predicate(),
                    not_hr_dept,
                )
            )
        else:
            clauses.append(
                and_(
                    Request.department_id == user.department_id,
                    non_hr_team_predicate(),
                    not_hr_dept,
                    Request.status.in_(list(_DEPT_VISIBLE_STATUSES)),
                )
            )

    if "reviewer" in roles:
        # Reviewers see pending review including HR-protected (for routing decisions)
        clauses.append(Request.status == RequestStatus.PENDING_REVIEW)

    if "hr" in roles:
        hr_clause = or_(
            Request.is_hr_sensitive.is_(True),
            Request.confidentiality == ConfidentialityLevel.HIGHLY_CONFIDENTIAL,
        )
        if hr_ids:
            hr_clause = or_(hr_clause, Request.department_id.in_(hr_ids))
        clauses.append(hr_clause)

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
        clauses.append(and_(non_hr_team_predicate(), not_hr_dept))

    return query.filter(or_(*clauses))


def true_clause():
    from sqlalchemy import true

    return true()
