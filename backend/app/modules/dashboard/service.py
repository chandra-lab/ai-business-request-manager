"""Role-scoped dashboard aggregations (Phase 6)."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.request import ConfidentialityLevel, Request, RequestStatus
from app.models.request_review_queue import RequestReviewQueue, ReviewQueueStatus
from app.models.user import User
from app.modules.requests import authz


def department_dashboard(db: Session, user: User) -> dict:
    """Team queue for department managers and department members."""
    if authz.is_admin(user):
        q = db.query(Request).filter(Request.is_hr_sensitive.is_(False))
    elif user.department_id:
        q = db.query(Request).filter(
            Request.is_hr_sensitive.is_(False),
            Request.department_id == user.department_id,
        )
        if not authz.is_manager(user):
            q = q.filter(
                Request.status.in_(
                    [
                        RequestStatus.PENDING_ASSIGNMENT,
                        RequestStatus.ASSIGNED,
                        RequestStatus.IN_PROGRESS,
                        RequestStatus.RESOLVED,
                    ]
                )
            )
    else:
        return {
            "pending_assignment_count": 0,
            "assigned_count": 0,
            "in_progress_count": 0,
            "resolved_count": 0,
            "recent": [],
        }

    def count_status(*statuses: RequestStatus) -> int:
        return int(
            q.filter(Request.status.in_(statuses))
            .with_entities(func.count(Request.id))
            .order_by(None)
            .scalar()
            or 0
        )

    recent = q.order_by(Request.updated_at.desc()).limit(15).all()
    return {
        "pending_assignment_count": count_status(RequestStatus.PENDING_ASSIGNMENT),
        "assigned_count": count_status(RequestStatus.ASSIGNED),
        "in_progress_count": count_status(RequestStatus.IN_PROGRESS),
        "resolved_count": count_status(RequestStatus.RESOLVED, RequestStatus.CLOSED),
        "recent": recent,
    }


def review_dashboard(db: Session, user: User) -> dict:
    if not (authz.is_reviewer(user) or authz.is_admin(user)):
        return {"open_count": 0, "in_review_count": 0, "items": []}

    open_count = (
        db.query(func.count(RequestReviewQueue.id))
        .filter(RequestReviewQueue.status == ReviewQueueStatus.OPEN)
        .scalar()
        or 0
    )
    in_review_count = (
        db.query(func.count(RequestReviewQueue.id))
        .filter(RequestReviewQueue.status == ReviewQueueStatus.IN_REVIEW)
        .scalar()
        or 0
    )
    items = (
        db.query(RequestReviewQueue)
        .filter(
            RequestReviewQueue.status.in_(
                [ReviewQueueStatus.OPEN, ReviewQueueStatus.IN_REVIEW]
            )
        )
        .order_by(RequestReviewQueue.created_at.asc())
        .limit(20)
        .all()
    )
    return {
        "open_count": int(open_count),
        "in_review_count": int(in_review_count),
        "items": items,
    }


def hr_dashboard(db: Session, user: User) -> dict:
    if not authz.is_hr(user):
        return {"case_count": 0, "highly_confidential_count": 0, "recent": []}

    case_count = int(
        db.query(func.count(Request.id))
        .filter(Request.is_hr_sensitive.is_(True))
        .scalar()
        or 0
    )
    highly = int(
        db.query(func.count(Request.id))
        .filter(
            Request.is_hr_sensitive.is_(True),
            Request.confidentiality == ConfidentialityLevel.HIGHLY_CONFIDENTIAL,
        )
        .scalar()
        or 0
    )
    recent = (
        db.query(Request)
        .filter(Request.is_hr_sensitive.is_(True))
        .order_by(Request.updated_at.desc())
        .limit(20)
        .all()
    )
    return {
        "case_count": case_count,
        "highly_confidential_count": highly,
        "recent": recent,
    }
