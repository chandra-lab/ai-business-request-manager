"""User directory helpers (admin)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.modules.requests import authz

router = APIRouter(prefix="/users", tags=["users"])


class UserBrief(BaseModel):
    id: UUID
    email: str
    full_name: str
    department_id: UUID | None
    roles: list[str] = []

    model_config = {"from_attributes": True}


@router.get("", response_model=list[UserBrief])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UserBrief]:
    if not authz.is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    users = db.query(User).filter(User.is_active.is_(True)).order_by(User.full_name.asc()).all()
    out: list[UserBrief] = []
    for u in users:
        out.append(
            UserBrief(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
                department_id=u.department_id,
                roles=u.role_names,
            )
        )
    return out
