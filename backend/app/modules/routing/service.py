"""Confidence-based routing after AI analysis (Phase 4)."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.ai_analysis import AIAnalysis, AIAnalysisStatus
from app.models.assignment import Assignment, AssignmentStatus
from app.models.audit_log import AuditLog
from app.models.request import ConfidentialityLevel, Request, RequestPriority, RequestStatus
from app.models.request_history import RequestHistory
from app.models.request_review_queue import RequestReviewQueue, ReviewQueueStatus
from app.modules.notifications.service import notify_department_managers, notify_user
from app.modules.requests.lifecycle import assert_transition

logger = get_logger(__name__)


class RoutingDecision(StrEnum):
    AUTO_ASSIGN = "auto_assign"
    HUMAN_REVIEW = "human_review"
    REVIEW_CLARIFICATION = "review_clarification"
    FAILURE_REVIEW = "failure_review"


def classify_confidence(confidence: float | None) -> RoutingDecision:
    settings = get_settings()
    if confidence is None:
        return RoutingDecision.FAILURE_REVIEW
    if confidence >= settings.routing_auto_assign_min:
        return RoutingDecision.AUTO_ASSIGN
    if confidence >= settings.routing_review_min:
        return RoutingDecision.HUMAN_REVIEW
    return RoutingDecision.REVIEW_CLARIFICATION


def _add_history(
    db: Session,
    request: Request,
    *,
    action: str,
    from_status: str | None,
    to_status: str | None,
    details: str | None = None,
    actor_id: UUID | None = None,
) -> None:
    db.add(
        RequestHistory(
            request_id=request.id,
            actor_id=actor_id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            details=details,
        )
    )


def _audit_priority(
    db: Session,
    *,
    request: Request,
    ai_priority: str | None,
) -> None:
    """Keep AI-recommended priority auditable and separate from system priority."""
    if not ai_priority:
        return
    system = request.priority.value
    if ai_priority.lower() != system:
        db.add(
            AuditLog(
                actor_id=None,
                action="priority.ai_vs_system",
                resource_type="request",
                resource_id=str(request.id),
                details=f"ai_recommended_priority={ai_priority}; system_priority={system}",
                metadata_json={
                    "ai_recommended_priority": ai_priority,
                    "system_priority": system,
                },
            )
        )


def _ensure_department_assignment(
    db: Session,
    *,
    request: Request,
    department_id: UUID,
) -> Assignment:
    """Idempotent department-only assignment (no individual employee)."""
    active = (
        db.query(Assignment)
        .filter(
            Assignment.request_id == request.id,
            Assignment.status == AssignmentStatus.ACTIVE,
        )
        .first()
    )
    if active and active.department_id == department_id and active.assignee_id is None:
        return active
    if active:
        active.status = AssignmentStatus.REASSIGNED

    assignment = Assignment(
        request_id=request.id,
        department_id=department_id,
        assignee_id=None,
        assigned_by_id=None,
        status=AssignmentStatus.ACTIVE,
        notes="Auto department assignment (Phase 4)",
    )
    db.add(assignment)
    return assignment


def _open_review(
    db: Session,
    *,
    request: Request,
    reason: str,
    details: str | None,
    clarification_required: bool,
) -> RequestReviewQueue:
    existing = (
        db.query(RequestReviewQueue)
        .filter(
            RequestReviewQueue.request_id == request.id,
            RequestReviewQueue.status.in_(
                [ReviewQueueStatus.OPEN, ReviewQueueStatus.IN_REVIEW]
            ),
        )
        .first()
    )
    if existing:
        existing.reason = reason
        existing.details = details
        existing.clarification_required = clarification_required
        return existing

    item = RequestReviewQueue(
        request_id=request.id,
        reason=reason,
        details=details,
        clarification_required=clarification_required,
        status=ReviewQueueStatus.OPEN,
    )
    db.add(item)
    return item


def apply_routing_after_analysis(
    db: Session,
    *,
    request: Request,
    analysis: AIAnalysis,
) -> RoutingDecision:
    """Route a request after AI completes or fails. Idempotent if already routed."""
    if request.status not in {
        RequestStatus.AI_PROCESSING,
        RequestStatus.SUBMITTED,
    }:
        # Already past routing handoff
        return RoutingDecision.AUTO_ASSIGN

    _audit_priority(db, request=request, ai_priority=analysis.recommended_priority)

    if analysis.status == AIAnalysisStatus.FAILED:
        decision = RoutingDecision.FAILURE_REVIEW
        previous = request.status
        assert_transition(previous, RequestStatus.PENDING_REVIEW)
        request.status = RequestStatus.PENDING_REVIEW
        request.clarification_required = False
        _open_review(
            db,
            request=request,
            reason="ai_failure",
            details=analysis.error_message or "AI analysis failed; manual review required",
            clarification_required=False,
        )
        _add_history(
            db,
            request,
            action="routed_to_review",
            from_status=previous.value,
            to_status=request.status.value,
            details="Persistent AI failure → manual review",
        )
        return decision

    confidence = float(analysis.confidence) if analysis.confidence is not None else None
    decision = classify_confidence(confidence)

    # HR-sensitive → highly confidential + force review (Phase 4 lite)
    if request.is_hr_sensitive or (
        analysis.raw_response and analysis.raw_response.get("is_hr_sensitive")
    ):
        request.is_hr_sensitive = True
        request.confidentiality = ConfidentialityLevel.HIGHLY_CONFIDENTIAL
        if decision == RoutingDecision.AUTO_ASSIGN:
            decision = RoutingDecision.HUMAN_REVIEW

    if (
        decision == RoutingDecision.AUTO_ASSIGN
        and analysis.recommended_department_id is not None
    ):
        previous = request.status
        assert_transition(previous, RequestStatus.PENDING_ASSIGNMENT)
        request.department_id = analysis.recommended_department_id
        request.status = RequestStatus.PENDING_ASSIGNMENT
        request.clarification_required = False
        _ensure_department_assignment(
            db,
            request=request,
            department_id=analysis.recommended_department_id,
        )
        _add_history(
            db,
            request,
            action="auto_routed_department",
            from_status=previous.value,
            to_status=request.status.value,
            details=(
                f"confidence={confidence} threshold_auto="
                f"{get_settings().routing_auto_assign_min}"
            ),
        )
        notify_department_managers(
            db,
            department_id=analysis.recommended_department_id,
            request_id=request.id,
            title="New request pending assignment",
            body=f"Request '{request.title}' was auto-routed to your department.",
        )
        return decision

    # Missing department on high confidence → treat as review
    if decision == RoutingDecision.AUTO_ASSIGN:
        decision = RoutingDecision.HUMAN_REVIEW

    clarification = decision == RoutingDecision.REVIEW_CLARIFICATION
    previous = request.status
    assert_transition(previous, RequestStatus.PENDING_REVIEW)
    request.status = RequestStatus.PENDING_REVIEW
    request.clarification_required = clarification
    reason = (
        "low_confidence_clarification"
        if clarification
        else ("medium_confidence" if decision == RoutingDecision.HUMAN_REVIEW else "routing_review")
    )
    _open_review(
        db,
        request=request,
        reason=reason,
        details=(
            f"confidence={confidence}; "
            f"recommended_department_id={analysis.recommended_department_id}"
        ),
        clarification_required=clarification,
    )
    _add_history(
        db,
        request,
        action="routed_to_review",
        from_status=previous.value,
        to_status=request.status.value,
        details=f"decision={decision.value} confidence={confidence}",
    )
    return decision


def assign_department_from_review(
    db: Session,
    *,
    review_id: UUID,
    reviewer_id: UUID,
    department_id: UUID,
    decision_reason: str,
    final_priority: RequestPriority | None = None,
) -> Request:
    review = db.query(RequestReviewQueue).filter(RequestReviewQueue.id == review_id).first()
    if review is None:
        raise ValueError("Review item not found")
    if review.status not in {ReviewQueueStatus.OPEN, ReviewQueueStatus.IN_REVIEW}:
        raise ValueError("Review item is not open")

    request = db.query(Request).filter(Request.id == review.request_id).with_for_update().first()
    if request is None:
        raise ValueError("Request not found")

    from datetime import UTC, datetime

    previous = request.status
    assert_transition(previous, RequestStatus.PENDING_ASSIGNMENT)
    if final_priority is not None and final_priority != request.priority:
        db.add(
            AuditLog(
                actor_id=reviewer_id,
                action="priority.reviewer_override",
                resource_type="request",
                resource_id=str(request.id),
                details=f"from={request.priority.value} to={final_priority.value}",
                metadata_json={
                    "previous_priority": request.priority.value,
                    "final_priority": final_priority.value,
                },
            )
        )
        request.priority = final_priority

    request.department_id = department_id
    request.status = RequestStatus.PENDING_ASSIGNMENT
    request.clarification_required = False
    _ensure_department_assignment(db, request=request, department_id=department_id)

    review.status = ReviewQueueStatus.RESOLVED
    review.decision = "assign_department"
    review.decision_reason = decision_reason
    review.assigned_department_id = department_id
    review.resolved_by_id = reviewer_id
    review.resolved_at = datetime.now(UTC)

    _add_history(
        db,
        request,
        action="review_assigned_department",
        from_status=previous.value,
        to_status=request.status.value,
        details=decision_reason,
        actor_id=reviewer_id,
    )
    notify_department_managers(
        db,
        department_id=department_id,
        request_id=request.id,
        title="Request assigned to department after review",
        body=f"Request '{request.title}' needs an individual assignee.",
    )
    db.commit()
    db.refresh(request)
    return request


def request_information_from_review(
    db: Session,
    *,
    review_id: UUID,
    reviewer_id: UUID,
    message: str,
) -> Request:
    from datetime import UTC, datetime

    review = db.query(RequestReviewQueue).filter(RequestReviewQueue.id == review_id).first()
    if review is None:
        raise ValueError("Review item not found")
    request = db.query(Request).filter(Request.id == review.request_id).with_for_update().first()
    if request is None:
        raise ValueError("Request not found")

    request.clarification_required = True
    review.clarification_required = True
    review.status = ReviewQueueStatus.IN_REVIEW
    review.decision = "request_information"
    review.decision_reason = message
    review.resolved_by_id = None
    review.resolved_at = None

    _add_history(
        db,
        request,
        action="review_request_information",
        from_status=request.status.value,
        to_status=request.status.value,
        details=message,
        actor_id=reviewer_id,
    )
    notify_user(
        db,
        user_id=request.requester_id,
        request_id=request.id,
        type="clarification_requested",
        title="More information needed",
        body=message,
    )
    db.commit()
    db.refresh(request)
    return request
