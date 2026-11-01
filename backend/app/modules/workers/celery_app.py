"""Celery application stub for Phase 1.

Phase 3+ will consume outbox messages for AI analysis and assignment.
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "aibrm",
    broker=settings.broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_hijack_root_logger=False,
    broker_connection_retry_on_startup=True,
)

# Import tasks so Celery registers them
celery_app.autodiscover_tasks(["app.modules.workers"])


@celery_app.task(name="aibrm.ping")
def ping() -> str:
    """Health-style stub task so the worker process starts cleanly."""
    return "pong"
