"""Celery tasks for outbox drain, AI analysis, and reliability."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.models.outbox_message import OutboxMessage, OutboxStatus
from app.models.request import Request, RequestStatus
from app.models.request_history import RequestHistory
from app.models.request_review_queue import RequestReviewQueue, ReviewQueueStatus
from app.modules.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="aibrm.ping")
def ping() -> str:
    return "pong"


def _send_to_manual_review(db, *, request_id: UUID, reason: str, details: str) -> None:
    request = db.query(Request).filter(Request.id == request_id).with_for_update().first()
    if request is None:
        return
    if request.status in {
        RequestStatus.PENDING_REVIEW,
        RequestStatus.PENDING_ASSIGNMENT,
        RequestStatus.ASSIGNED,
        RequestStatus.CLOSED,
        RequestStatus.CANCELLED,
    }:
        return
    previous = request.status
    request.status = RequestStatus.PENDING_REVIEW
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
    if existing is None:
        db.add(
            RequestReviewQueue(
                request_id=request.id,
                reason=reason,
                details=details,
                clarification_required=False,
                status=ReviewQueueStatus.OPEN,
            )
        )
    db.add(
        RequestHistory(
            request_id=request.id,
            actor_id=None,
            action="routed_to_review",
            from_status=previous.value,
            to_status=request.status.value,
            details=details,
        )
    )
    db.commit()


@celery_app.task(name="aibrm.process_outbox_message", bind=True, max_retries=8)
def process_outbox_message(self, outbox_id: str) -> dict:
    """Consume one transactional outbox row and run AI analysis + routing."""
    from app.ai.service import process_request_analysis

    settings = get_settings()
    db = SessionLocal()
    try:
        msg = db.query(OutboxMessage).filter(OutboxMessage.id == UUID(outbox_id)).first()
        if msg is None:
            return {"status": "missing"}
        if msg.status == OutboxStatus.PUBLISHED:
            return {"status": "already_published", "outbox_id": outbox_id}
        if msg.event_type != "request.submitted":
            msg.status = OutboxStatus.DEAD
            msg.last_error = f"Unsupported event_type={msg.event_type}"
            db.commit()
            return {"status": "unsupported"}

        request_id = UUID(str(msg.payload.get("request_id") or msg.aggregate_id))
        try:
            analysis = process_request_analysis(db, request_id=request_id)
            msg = db.query(OutboxMessage).filter(OutboxMessage.id == UUID(outbox_id)).first()
            if msg is not None:
                msg.status = OutboxStatus.PUBLISHED
                msg.attempts = (msg.attempts or 0) + 1
                msg.processed_at = datetime.now(UTC)
                msg.last_error = None
                db.commit()
            return {
                "status": "ok",
                "analysis_id": str(analysis.id),
                "analysis_status": analysis.status.value,
            }
        except Exception as exc:  # noqa: BLE001
            msg = db.query(OutboxMessage).filter(OutboxMessage.id == UUID(outbox_id)).first()
            attempts = (msg.attempts or 0) + 1 if msg else 1
            max_attempts = settings.outbox_max_attempts
            if msg is not None:
                msg.attempts = attempts
                msg.last_error = str(exc)[:2000]
                msg.status = OutboxStatus.FAILED
                db.commit()

            if attempts >= max_attempts:
                logger.error(
                    "Outbox %s exhausted retries (%s); sending request to manual review",
                    outbox_id,
                    attempts,
                )
                _send_to_manual_review(
                    db,
                    request_id=request_id,
                    reason="outbox_exhausted",
                    details=f"Outbox failed after {attempts} attempts: {exc}",
                )
                msg = db.query(OutboxMessage).filter(OutboxMessage.id == UUID(outbox_id)).first()
                if msg is not None:
                    msg.status = OutboxStatus.DEAD
                    db.commit()
                return {"status": "dead_letter_review", "attempts": attempts}

            countdown = min(120, 2 ** max(self.request.retries, 0))
            logger.exception(
                "Outbox processing failed for %s (attempt %s); retry in %ss",
                outbox_id,
                attempts,
                countdown,
            )
            raise self.retry(exc=exc, countdown=countdown)
    finally:
        db.close()


@celery_app.task(name="aibrm.drain_outbox")
def drain_outbox(limit: int = 20) -> dict:
    """Pick up pending/failed-retryable outbox rows."""
    db = SessionLocal()
    try:
        pending = (
            db.query(OutboxMessage)
            .filter(
                OutboxMessage.status.in_([OutboxStatus.PENDING, OutboxStatus.FAILED]),
                OutboxMessage.event_type == "request.submitted",
            )
            .order_by(OutboxMessage.created_at.asc())
            .limit(limit)
            .all()
        )
        ids = []
        for m in pending:
            if (m.attempts or 0) >= get_settings().outbox_max_attempts:
                continue
            ids.append(str(m.id))
    finally:
        db.close()

    for oid in ids:
        process_outbox_message.delay(oid)
    return {"enqueued": len(ids)}
