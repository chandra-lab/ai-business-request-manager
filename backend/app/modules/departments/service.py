"""Department admin operations.

Delete policy
-------------
Prefer **soft-delete** (`is_active=False`) so existing requests/assignments stay
visible and FK history is preserved. Hard delete runs only when the department
has no referencing requests, assignments, users, AI analyses, or review-queue
assignments. Inactive departments are excluded from new auto-routing (AI lookup
and confidence auto-assign) but remain listable to admins.
"""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.ai_analysis import AIAnalysis
from app.models.assignment import Assignment
from app.models.department import Department
from app.models.request import Request
from app.models.request_review_queue import RequestReviewQueue
from app.models.role import Role, UserRole
from app.models.user import User
from app.modules.requests import authz


def _slug_code(name: str) -> str:
    raw = re.sub(r"[^A-Za-z0-9]+", "_", name.strip().upper()).strip("_")
    return (raw or "DEPT")[:32]


def _unique_code(db: Session, base: str) -> str:
    code = base[:32]
    n = 2
    while db.query(Department).filter(Department.code == code).first() is not None:
        suffix = f"_{n}"
        code = f"{base[: 32 - len(suffix)]}{suffix}"
        n += 1
    return code


def _require_admin(actor: User) -> None:
    if not authz.is_admin(actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")


def _get_department(db: Session, department_id: UUID) -> Department:
    dept = db.query(Department).filter(Department.id == department_id).first()
    if dept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return dept


def _ensure_manager_role(db: Session, manager: User, dept: Department) -> None:
    manager.department_id = dept.id
    role = db.query(Role).filter(Role.name == "department_manager").first()
    if role is None:
        return
    has = (
        db.query(UserRole)
        .filter(UserRole.user_id == manager.id, UserRole.role_id == role.id)
        .first()
    )
    if has is None:
        db.add(UserRole(user_id=manager.id, role_id=role.id))


def _resolve_manager(db: Session, manager_user_id: UUID | None) -> User | None:
    if manager_user_id is None:
        return None
    manager = db.query(User).filter(User.id == manager_user_id, User.is_active.is_(True)).first()
    if manager is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manager user not found")
    return manager


def list_departments(db: Session, *, include_inactive: bool = False) -> list[Department]:
    q = db.query(Department)
    if not include_inactive:
        q = q.filter(Department.is_active.is_(True))
    return q.order_by(Department.name.asc()).all()


def create_department(
    db: Session,
    *,
    actor: User,
    name: str,
    description: str | None = None,
    manager_user_id: UUID | None = None,
    code: str | None = None,
) -> Department:
    _require_admin(actor)

    clean_name = name.strip()
    if len(clean_name) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name too short")

    existing = db.query(Department).filter(Department.name == clean_name).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Department name already exists: {clean_name}",
        )

    if code:
        dept_code = re.sub(r"[^A-Za-z0-9_]+", "_", code.strip().upper())[:32]
        if db.query(Department).filter(Department.code == dept_code).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Code already exists")
    else:
        dept_code = _unique_code(db, _slug_code(clean_name))

    manager = _resolve_manager(db, manager_user_id)

    dept = Department(
        name=clean_name,
        code=dept_code,
        description=(description or "").strip() or None,
        is_active=True,
        manager_user_id=manager.id if manager else None,
    )
    db.add(dept)
    db.flush()

    if manager is not None:
        _ensure_manager_role(db, manager, dept)

    db.commit()
    db.refresh(dept)
    return dept


def update_department(
    db: Session,
    *,
    actor: User,
    department_id: UUID,
    fields: dict,
) -> Department:
    """Update name, description, manager_user_id, and/or is_active. Admin only.

    ``fields`` should only contain keys the client explicitly set (exclude_unset).
    """
    _require_admin(actor)
    dept = _get_department(db, department_id)

    if "name" in fields and fields["name"] is not None:
        clean_name = str(fields["name"]).strip()
        if len(clean_name) < 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name too short")
        clash = (
            db.query(Department)
            .filter(Department.name == clean_name, Department.id != dept.id)
            .first()
        )
        if clash is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Department name already exists: {clean_name}",
            )
        dept.name = clean_name

    if "description" in fields:
        raw = fields["description"]
        dept.description = None if raw is None else (str(raw).strip() or None)

    if "manager_user_id" in fields:
        mid = fields["manager_user_id"]
        if mid is None:
            dept.manager_user_id = None
        else:
            manager = _resolve_manager(db, mid if isinstance(mid, UUID) else UUID(str(mid)))
            assert manager is not None
            dept.manager_user_id = manager.id
            _ensure_manager_role(db, manager, dept)

    if "is_active" in fields and fields["is_active"] is not None:
        dept.is_active = bool(fields["is_active"])

    db.commit()
    db.refresh(dept)
    return dept


def _has_blocking_references(db: Session, department_id: UUID) -> bool:
    if db.query(Request.id).filter(Request.department_id == department_id).first():
        return True
    if db.query(Assignment.id).filter(Assignment.department_id == department_id).first():
        return True
    if db.query(User.id).filter(User.department_id == department_id).first():
        return True
    if (
        db.query(AIAnalysis.id)
        .filter(AIAnalysis.recommended_department_id == department_id)
        .first()
    ):
        return True
    if (
        db.query(RequestReviewQueue.id)
        .filter(RequestReviewQueue.assigned_department_id == department_id)
        .first()
    ):
        return True
    return False


def delete_department(
    db: Session,
    *,
    actor: User,
    department_id: UUID,
) -> tuple[Department | None, str]:
    """Soft-delete unless hard delete is safe.

    Returns ``(department_or_none, mode)`` where mode is ``soft`` or ``hard``.
    Soft-deleted rows are returned; hard-deleted returns ``(None, "hard")``.
    """
    _require_admin(actor)
    dept = _get_department(db, department_id)

    if _has_blocking_references(db, department_id):
        dept.is_active = False
        db.commit()
        db.refresh(dept)
        return dept, "soft"

    db.delete(dept)
    db.commit()
    return None, "hard"
