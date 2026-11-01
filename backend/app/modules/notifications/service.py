"""Create in-app notification records."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.role import Role, UserRole
from app.models.user import User


def notify_user(
    db: Session,
    *,
    user_id: UUID,
    request_id: UUID | None,
    type: str,
    title: str,
    body: str,
) -> Notification:
    note = Notification(
        user_id=user_id,
        request_id=request_id,
        type=type,
        title=title,
        body=body,
    )
    db.add(note)
    return note


def notify_department_managers(
    db: Session,
    *,
    department_id: UUID,
    request_id: UUID,
    title: str,
    body: str,
) -> int:
    """Notify users with department_manager role in the given department."""
    managers = (
        db.query(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(
            User.department_id == department_id,
            User.is_active.is_(True),
            Role.name == "department_manager",
        )
        .all()
    )
    for mgr in managers:
        notify_user(
            db,
            user_id=mgr.id,
            request_id=request_id,
            type="department_pending_assignment",
            title=title,
            body=body,
        )
    return len(managers)
