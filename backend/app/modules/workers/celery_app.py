"""Celery application for AIBRM workers."""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "aibrm",
    broker=settings.broker_url,
    backend=settings.celery_result_backend,
    include=["app.modules.workers.tasks"],
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
    beat_schedule={
        # Safety net for pending outbox rows
        "drain-outbox-every-minute": {
            "task": "aibrm.drain_outbox",
            "schedule": 60.0,
        },
    },
)
