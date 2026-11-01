"""Department manager assignment APIs (Phase 4)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.modules.assignments.service import assign_employee, list_manager_queue
from app.modules.requests import authz
from app.modules.requests.service import get_request_or_404
from app.schemas.requests import RequestSummary
from app.schemas.routing import AssignEmployeeBody, AssignmentOut, NotificationOut

router = APIRouter(tags=["manager"])


@router.get("/manager/queue", response_model=list[RequestSummary])
def manager_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RequestSummary]:
    if not (authz.is_manager(current_user) or authz.is_admin(current_user)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager role required")
    items = list_manager_queue(db, current_user)
    return [RequestSummary.model_validate(i) for i in items]


@router.post("/requests/{request_id}/assign", response_model=AssignmentOut)
def assign_request(
    request_id: UUID,
    body: AssignEmployeeBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssignmentOut:
    request = get_request_or_404(db, request_id)
    assignment = assign_employee(
        db,
        request=request,
        manager=current_user,
        assignee_id=body.assignee_id,
        notes=body.notes,
    )
    return AssignmentOut.model_validate(assignment)


@router.post("/requests/{request_id}/reassign", response_model=AssignmentOut)
def reassign_request(
    request_id: UUID,
    body: AssignEmployeeBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssignmentOut:
    """Reassign is the same path as assign with a different assignee (marks prior REASSIGNED)."""
    request = get_request_or_404(db, request_id)
    assignment = assign_employee(
        db,
        request=request,
        manager=current_user,
        assignee_id=body.assignee_id,
        notes=body.notes or "Reassignment",
    )
    return AssignmentOut.model_validate(assignment)


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[NotificationOut]:
    items = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return [NotificationOut.model_validate(i) for i in items]
