"""Department admin operations."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.department import Department
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
    if not authz.is_admin(actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")

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

    manager: User | None = None
    if manager_user_id is not None:
        manager = db.query(User).filter(User.id == manager_user_id, User.is_active.is_(True)).first()
        if manager is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manager user not found")

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
        manager.department_id = dept.id
        # Ensure department_manager role
        role = db.query(Role).filter(Role.name == "department_manager").first()
        if role is not None:
            has = (
                db.query(UserRole)
                .filter(UserRole.user_id == manager.id, UserRole.role_id == role.id)
                .first()
            )
            if has is None:
                db.add(UserRole(user_id=manager.id, role_id=role.id))

    db.commit()
    db.refresh(dept)
    return dept
