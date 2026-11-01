"""Department list (Phase 4 helper for review UI)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.department import Department
from app.models.user import User

router = APIRouter(prefix="/departments", tags=["departments"])


class DepartmentOut(BaseModel):
    id: UUID
    code: str
    name: str

    model_config = {"from_attributes": True}


@router.get("", response_model=list[DepartmentOut])
def list_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DepartmentOut]:
    _ = current_user
    items = (
        db.query(Department)
        .filter(Department.is_active.is_(True))
        .order_by(Department.code.asc())
        .all()
    )
    return [DepartmentOut.model_validate(i) for i in items]
