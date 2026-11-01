"""Seed departments, roles, and demo users for local development.

Demo passwords come from SEED_DEMO_PASSWORD (see .env.example / README).
This script is idempotent — safe to re-run.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `python -m scripts.seed` from backend/
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.models.department import Department
from app.models.role import Role, UserRole
from app.models.user import User

logger = get_logger(__name__)

DEPARTMENTS = [
    {
        "code": "HR",
        "name": "Human Resources",
        "description": "People operations, employee relations, and sensitive HR cases.",
    },
    {
        "code": "IT",
        "name": "Information Technology",
        "description": "Systems, access, hardware, and digital workplace support.",
    },
    {
        "code": "FIN",
        "name": "Finance",
        "description": "Budgets, invoices, purchasing, and financial controls.",
    },
    {
        "code": "FLEET",
        "name": "Fleet Operations",
        "description": "Vehicle logistics, maintenance scheduling, and dealer fleet support.",
    },
    {
        "code": "LEGAL",
        "name": "Legal & Compliance",
        "description": "Contracts, regulatory compliance, and policy exceptions.",
    },
]

ROLES = [
    ("employee", "Standard employee who submits and tracks requests"),
    ("department_manager", "Manages assignments within a department"),
    ("reviewer", "Handles low-confidence AI routing in the review queue"),
    ("hr", "HR specialist with access to HR-sensitive cases and notes"),
    ("admin", "System administrator"),
]

# email, full_name, department_code, roles
DEMO_USERS = [
    ("employee@aibrm.example.com", "Eva Employee", "IT", ["employee"]),
    ("manager@aibrm.example.com", "Morgan Manager", "FLEET", ["employee", "department_manager"]),
    ("reviewer@aibrm.example.com", "Riley Reviewer", "LEGAL", ["employee", "reviewer"]),
    ("hr@aibrm.example.com", "Harper HR", "HR", ["employee", "hr"]),
    ("admin@aibrm.example.com", "Alex Admin", "IT", ["employee", "admin"]),
]


def _get_or_create_department(db: Session, data: dict) -> Department:
    dept = db.query(Department).filter(Department.code == data["code"]).first()
    if dept:
        dept.name = data["name"]
        dept.description = data["description"]
        dept.is_active = True
        return dept
    dept = Department(
        code=data["code"],
        name=data["name"],
        description=data["description"],
        is_active=True,
    )
    db.add(dept)
    db.flush()
    return dept


def _get_or_create_role(db: Session, name: str, description: str) -> Role:
    role = db.query(Role).filter(Role.name == name).first()
    if role:
        role.description = description
        return role
    role = Role(name=name, description=description)
    db.add(role)
    db.flush()
    return role


def _get_or_create_user(
    db: Session,
    *,
    email: str,
    full_name: str,
    password: str,
    department: Department | None,
    roles: list[Role],
) -> User:
    user = db.query(User).filter(User.email == email.lower()).first()
    if user is None:
        user = User(
            email=email.lower(),
            full_name=full_name,
            password_hash=hash_password(password),
            department_id=department.id if department else None,
            is_active=True,
        )
        db.add(user)
        db.flush()
    else:
        user.full_name = full_name
        user.password_hash = hash_password(password)
        user.department_id = department.id if department else None
        user.is_active = True

    existing_role_ids = {ur.role_id for ur in user.user_roles}
    for role in roles:
        if role.id not in existing_role_ids:
            db.add(UserRole(user_id=user.id, role_id=role.id))
    return user


def seed(db: Session) -> None:
    settings = get_settings()
    password = settings.seed_demo_password

    departments = {_d["code"]: _get_or_create_department(db, _d) for _d in DEPARTMENTS}
    roles = {name: _get_or_create_role(db, name, desc) for name, desc in ROLES}

    for email, full_name, dept_code, role_names in DEMO_USERS:
        _get_or_create_user(
            db,
            email=email,
            full_name=full_name,
            password=password,
            department=departments.get(dept_code),
            roles=[roles[r] for r in role_names],
        )

    db.commit()
    logger.info(
        "Seed complete: %d departments, %d roles, %d demo users",
        len(departments),
        len(roles),
        len(DEMO_USERS),
    )


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
