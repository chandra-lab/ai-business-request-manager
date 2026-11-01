"""Department list + admin create."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.modules.departments import service as dept_service
from app.modules.requests import authz

router = APIRouter(prefix="/departments", tags=["departments"])


class DepartmentOut(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None = None
    is_active: bool = True
    manager_user_id: UUID | None = None

    model_config = {"from_attributes": True}


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    manager_user_id: UUID | None = None
    code: str | None = Field(default=None, max_length=32, description="Optional short code; auto from name")


@router.get("", response_model=list[DepartmentOut])
def list_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DepartmentOut]:
    include_inactive = authz.is_admin(current_user)
    items = dept_service.list_departments(db, include_inactive=include_inactive)
    return [DepartmentOut.model_validate(i) for i in items]


@router.post("", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(
    body: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DepartmentOut:
    dept = dept_service.create_department(
        db,
        actor=current_user,
        name=body.name,
        description=body.description,
        manager_user_id=body.manager_user_id,
        code=body.code,
    )
    return DepartmentOut.model_validate(dept)
