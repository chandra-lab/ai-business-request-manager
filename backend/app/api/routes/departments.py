"""Department list + admin create/update/delete + members."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.department import Department
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


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    manager_user_id: UUID | None = None
    is_active: bool | None = None


class DepartmentDeleteOut(BaseModel):
    id: UUID | None = None
    deletion: str  # "soft" | "hard"
    department: DepartmentOut | None = None


class DepartmentMemberOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    department_id: UUID | None = None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[DepartmentOut])
def list_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DepartmentOut]:
    include_inactive = authz.is_admin(current_user)
    items = dept_service.list_departments(db, include_inactive=include_inactive)
    return [DepartmentOut.model_validate(i) for i in items]


@router.get("/{department_id}/members", response_model=list[DepartmentMemberOut])
def list_department_members(
    department_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DepartmentMemberOut]:
    """Active members of a department — used by reviewer assignee picker."""
    if not (
        authz.is_admin(current_user)
        or authz.is_reviewer(current_user)
        or authz.is_manager(current_user)
        or (
            current_user.department_id is not None
            and current_user.department_id == department_id
        )
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    dept = db.query(Department).filter(Department.id == department_id).first()
    if dept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    members = dept_service.list_active_members(db, department_id=department_id)
    return [DepartmentMemberOut.model_validate(u) for u in members]


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


@router.patch("/{department_id}", response_model=DepartmentOut)
def update_department(
    department_id: UUID,
    body: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DepartmentOut:
    fields = body.model_dump(exclude_unset=True)
    dept = dept_service.update_department(
        db,
        actor=current_user,
        department_id=department_id,
        fields=fields,
    )
    return DepartmentOut.model_validate(dept)


@router.delete("/{department_id}", response_model=DepartmentDeleteOut)
def delete_department(
    department_id: UUID,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DepartmentDeleteOut:
    dept, mode = dept_service.delete_department(
        db,
        actor=current_user,
        department_id=department_id,
    )
    if mode == "hard":
        response.status_code = status.HTTP_200_OK
        return DepartmentDeleteOut(id=department_id, deletion="hard", department=None)
    assert dept is not None
    return DepartmentDeleteOut(
        id=dept.id,
        deletion="soft",
        department=DepartmentOut.model_validate(dept),
    )
