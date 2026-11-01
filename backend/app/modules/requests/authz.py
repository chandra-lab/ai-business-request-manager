"""Request visibility and mutation authorization (Phase 2 scope)."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.request import Request, RequestStatus
from app.models.user import User


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


def can_view_request(user: User, request: Request) -> bool:
    if is_admin(user):
        return True
    if request.requester_id == user.id:
        return True
    if is_manager(user) and user.department_id and request.department_id == user.department_id:
        return True
    if is_reviewer(user) and request.status == RequestStatus.PENDING_REVIEW:
        return True
    if is_hr(user) and request.is_hr_sensitive:
        return True
    return False


def require_view(user: User, request: Request) -> None:
    if not can_view_request(user, request):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")


def can_edit_as_requester(user: User, request: Request) -> bool:
    return request.requester_id == user.id


def apply_list_scope(query: Any, user: User, db: Session) -> Any:
    """Restrict list queries by role. Employees see own; managers see dept; etc."""
    _ = db
    if is_admin(user):
        return query

    roles = role_set(user)
    clauses = [Request.requester_id == user.id]

    if "department_manager" in roles and user.department_id is not None:
        clauses.append(Request.department_id == user.department_id)

    if "reviewer" in roles:
        clauses.append(Request.status == RequestStatus.PENDING_REVIEW)

    if "hr" in roles:
        clauses.append(Request.is_hr_sensitive.is_(True))

    return query.filter(or_(*clauses))
