"""Celery tasks for outbox drain and AI analysis."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.models.outbox_message import OutboxMessage, OutboxStatus
from app.modules.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="aibrm.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="aibrm.process_outbox_message", bind=True, max_retries=5)
def process_outbox_message(self, outbox_id: str) -> dict:
    """Consume one transactional outbox row and run AI analysis once."""
    from app.ai.service import process_request_analysis

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
            # Re-bind outbox after analysis commit
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
            if msg is not None:
                msg.attempts = (msg.attempts or 0) + 1
                msg.last_error = str(exc)[:2000]
                msg.status = OutboxStatus.FAILED
                db.commit()
            logger.exception("Outbox processing failed for %s", outbox_id)
            raise self.retry(exc=exc, countdown=min(60, 2 ** max(self.request.retries, 0)))
    finally:
        db.close()


@celery_app.task(name="aibrm.drain_outbox")
def drain_outbox(limit: int = 20) -> dict:
    """Pick up pending outbox rows (safety net if immediate enqueue was missed)."""
    db = SessionLocal()
    try:
        pending = (
            db.query(OutboxMessage)
            .filter(
                OutboxMessage.status == OutboxStatus.PENDING,
                OutboxMessage.event_type == "request.submitted",
            )
            .order_by(OutboxMessage.created_at.asc())
            .limit(limit)
            .all()
        )
        ids = [str(m.id) for m in pending]
    finally:
        db.close()

    for oid in ids:
        process_outbox_message.delay(oid)
    return {"enqueued": len(ids)}
