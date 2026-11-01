"""Human review queue APIs (Phase 4)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.request_review_queue import RequestReviewQueue, ReviewQueueStatus
from app.models.user import User
from app.modules.requests import authz
from app.modules.routing.service import (
    assign_department_from_review,
    request_information_from_review,
)
from app.schemas.requests import RequestSummary
from app.schemas.routing import (
    AssignDepartmentBody,
    RequestInformationBody,
    ReviewQueueItem,
)

router = APIRouter(prefix="/review-queue", tags=["review-queue"])


def _require_reviewer(user: User) -> None:
    if not (authz.is_reviewer(user) or authz.is_admin(user)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer role required")


@router.get("", response_model=list[ReviewQueueItem])
def list_review_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ReviewQueueItem]:
    _require_reviewer(current_user)
    items = (
        db.query(RequestReviewQueue)
        .options(joinedload(RequestReviewQueue.request))
        .filter(
            RequestReviewQueue.status.in_(
                [ReviewQueueStatus.OPEN, ReviewQueueStatus.IN_REVIEW]
            )
        )
        .order_by(RequestReviewQueue.created_at.asc())
        .all()
    )
    out: list[ReviewQueueItem] = []
    for item in items:
        payload = ReviewQueueItem.model_validate(item)
        if item.request is not None:
            payload.request = RequestSummary.model_validate(item.request)
        out.append(payload)
    return out


def _open_review_for_request(db: Session, request_id: UUID) -> RequestReviewQueue | None:
    return (
        db.query(RequestReviewQueue)
        .options(joinedload(RequestReviewQueue.request))
        .filter(
            RequestReviewQueue.request_id == request_id,
            RequestReviewQueue.status.in_(
                [ReviewQueueStatus.OPEN, ReviewQueueStatus.IN_REVIEW]
            ),
        )
        .order_by(RequestReviewQueue.created_at.desc())
        .first()
    )


def _to_review_payload(item: RequestReviewQueue) -> ReviewQueueItem:
    payload = ReviewQueueItem.model_validate(item)
    if item.request is not None:
        payload.request = RequestSummary.model_validate(item.request)
    return payload


@router.get("/by-request/{request_id}", response_model=ReviewQueueItem)
def get_open_review_for_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewQueueItem:
    """Open review-queue row for a ticket (used by Jira-style detail Actions)."""
    _require_reviewer(current_user)
    item = _open_review_for_request(db, request_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No open review item")
    return _to_review_payload(item)


@router.post("/by-request/{request_id}/assign-department", response_model=RequestSummary)
def assign_department_by_request(
    request_id: UUID,
    body: AssignDepartmentBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RequestSummary:
    """Assign department from ticket detail without needing the review-queue id."""
    _require_reviewer(current_user)
    item = _open_review_for_request(db, request_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No open review item for this request",
        )
    try:
        request = assign_department_from_review(
            db,
            review_id=item.id,
            reviewer_id=current_user.id,
            department_id=body.department_id,
            decision_reason=body.decision_reason,
            final_priority=body.final_priority,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RequestSummary.model_validate(request)


@router.post("/by-request/{request_id}/request-information", response_model=RequestSummary)
def request_information_by_request(
    request_id: UUID,
    body: RequestInformationBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RequestSummary:
    _require_reviewer(current_user)
    item = _open_review_for_request(db, request_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No open review item for this request",
        )
    try:
        request = request_information_from_review(
            db,
            review_id=item.id,
            reviewer_id=current_user.id,
            message=body.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RequestSummary.model_validate(request)


@router.get("/{review_id}", response_model=ReviewQueueItem)
def get_review_item(
    review_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewQueueItem:
    _require_reviewer(current_user)
    item = (
        db.query(RequestReviewQueue)
        .options(joinedload(RequestReviewQueue.request))
        .filter(RequestReviewQueue.id == review_id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return _to_review_payload(item)


@router.post("/{review_id}/assign-department", response_model=RequestSummary)
def assign_department(
    review_id: UUID,
    body: AssignDepartmentBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RequestSummary:
    _require_reviewer(current_user)
    try:
        request = assign_department_from_review(
            db,
            review_id=review_id,
            reviewer_id=current_user.id,
            department_id=body.department_id,
            decision_reason=body.decision_reason,
            final_priority=body.final_priority,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RequestSummary.model_validate(request)


@router.post("/{review_id}/request-information", response_model=RequestSummary)
def request_information(
    review_id: UUID,
    body: RequestInformationBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RequestSummary:
    _require_reviewer(current_user)
    try:
        request = request_information_from_review(
            db,
            review_id=review_id,
            reviewer_id=current_user.id,
            message=body.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RequestSummary.model_validate(request)
