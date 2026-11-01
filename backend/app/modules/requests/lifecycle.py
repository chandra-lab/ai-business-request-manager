"""Validated request status transitions."""

from __future__ import annotations

from app.models.request import RequestStatus

ALLOWED_TRANSITIONS: dict[RequestStatus, set[RequestStatus]] = {
    RequestStatus.DRAFT: {RequestStatus.SUBMITTED, RequestStatus.CANCELLED},
    RequestStatus.SUBMITTED: {
        RequestStatus.AI_PROCESSING,
        RequestStatus.CANCELLED,
    },
    RequestStatus.AI_PROCESSING: {
        RequestStatus.PENDING_REVIEW,
        RequestStatus.PENDING_ASSIGNMENT,
        RequestStatus.CANCELLED,
    },
    RequestStatus.PENDING_REVIEW: {
        RequestStatus.PENDING_ASSIGNMENT,
        RequestStatus.CANCELLED,
    },
    RequestStatus.PENDING_ASSIGNMENT: {
        RequestStatus.ASSIGNED,
        RequestStatus.PENDING_REVIEW,
        RequestStatus.CANCELLED,
    },
    RequestStatus.ASSIGNED: {
        RequestStatus.IN_PROGRESS,
        RequestStatus.PENDING_ASSIGNMENT,
        RequestStatus.CANCELLED,
    },
    RequestStatus.IN_PROGRESS: {
        RequestStatus.RESOLVED,
        RequestStatus.CANCELLED,
    },
    RequestStatus.RESOLVED: {
        RequestStatus.CLOSED,
        RequestStatus.IN_PROGRESS,
    },
    RequestStatus.CLOSED: set(),
    RequestStatus.CANCELLED: set(),
}


def can_transition(current: RequestStatus, target: RequestStatus) -> bool:
    if current == target:
        return True
    return target in ALLOWED_TRANSITIONS.get(current, set())


def assert_transition(current: RequestStatus, target: RequestStatus) -> None:
    if not can_transition(current, target):
        raise ValueError(f"Invalid status transition: {current.value} → {target.value}")
