"""HR case notes and case-level access APIs (Phase 5)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.modules.hr import service as hr_service
from app.modules.requests.service import get_request_or_404
from app.schemas.hr import (
    HRCaseAccessGrant,
    HRCaseAccessOut,
    HRCaseNoteCreate,
    HRCaseNoteOut,
)

router = APIRouter(prefix="/requests", tags=["hr-security"])


@router.get("/{request_id}/hr-notes", response_model=list[HRCaseNoteOut])
def list_hr_notes(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[HRCaseNoteOut]:
    request = get_request_or_404(db, request_id)
    notes = hr_service.list_notes(db, user=current_user, request=request)
    return [HRCaseNoteOut.model_validate(n) for n in notes]


@router.post(
    "/{request_id}/hr-notes",
    response_model=HRCaseNoteOut,
    status_code=status.HTTP_201_CREATED,
)
def create_hr_note(
    request_id: UUID,
    body: HRCaseNoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HRCaseNoteOut:
    request = get_request_or_404(db, request_id)
    note = hr_service.add_note(db, user=current_user, request=request, content=body.content)
    return HRCaseNoteOut.model_validate(note)


@router.get("/{request_id}/hr-access", response_model=list[HRCaseAccessOut])
def list_hr_access(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[HRCaseAccessOut]:
    request = get_request_or_404(db, request_id)
    rows = hr_service.list_access(db, user=current_user, request=request)
    return [HRCaseAccessOut.model_validate(r) for r in rows]


@router.post(
    "/{request_id}/hr-access",
    response_model=HRCaseAccessOut,
    status_code=status.HTTP_201_CREATED,
)
def grant_hr_access(
    request_id: UUID,
    body: HRCaseAccessGrant,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HRCaseAccessOut:
    request = get_request_or_404(db, request_id)
    access = hr_service.grant_access(
        db, granter=current_user, request=request, grantee_id=body.user_id
    )
    return HRCaseAccessOut.model_validate(access)


@router.delete("/{request_id}/hr-access/{access_id}", response_model=HRCaseAccessOut)
def revoke_hr_access(
    request_id: UUID,
    access_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HRCaseAccessOut:
    request = get_request_or_404(db, request_id)
    access = hr_service.revoke_access(
        db, actor=current_user, request=request, access_id=access_id
    )
    return HRCaseAccessOut.model_validate(access)
