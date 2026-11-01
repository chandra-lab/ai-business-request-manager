"""Orchestrate AI analysis for a submitted request (idempotent)."""

from __future__ import annotations

import hashlib
import time
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.factory import get_ai_provider
from app.ai.interface import AIProvider
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.ai_analysis import AIAnalysis, AIAnalysisStatus
from app.models.department import Department
from app.models.request import Request, RequestStatus
from app.models.request_history import RequestHistory
from app.modules.routing.service import apply_routing_after_analysis

logger = get_logger(__name__)


def content_hash(title: str, description: str) -> str:
    digest = hashlib.sha256(f"{title}\n{description}".encode("utf-8")).hexdigest()
    return digest[:32]


def analysis_idempotency_key(request_id: UUID, title: str, description: str) -> str:
    return f"ai:{request_id}:{content_hash(title, description)}"


def process_request_analysis(
    db: Session,
    *,
    request_id: UUID,
    provider: AIProvider | None = None,
) -> AIAnalysis:
    """Run at most one AI call for the current request content; persist AIAnalysis; route.

    After analysis (Phase 4): confidence routing moves the request to
    ``pending_assignment`` (auto dept) or ``pending_review``.
    """
    request = db.query(Request).filter(Request.id == request_id).with_for_update().first()
    if request is None:
        raise ValueError(f"Request {request_id} not found")

    key = analysis_idempotency_key(request.id, request.title, request.description)
    existing = (
        db.query(AIAnalysis)
        .filter(
            AIAnalysis.idempotency_key == key,
            AIAnalysis.status == AIAnalysisStatus.COMPLETED,
        )
        .first()
    )
    if existing:
        logger.info("Skipping AI call; completed analysis %s already exists", existing.id)
        apply_routing_after_analysis(db, request=request, analysis=existing)
        db.commit()
        db.refresh(existing)
        return existing

    if request.status == RequestStatus.SUBMITTED:
        previous = request.status
        request.status = RequestStatus.AI_PROCESSING
        db.add(
            RequestHistory(
                request_id=request.id,
                actor_id=None,
                action="status_changed",
                from_status=previous.value,
                to_status=RequestStatus.AI_PROCESSING.value,
                details="AI worker started analysis",
            )
        )
        db.flush()

    settings = get_settings()
    ai = provider or get_ai_provider()
    started = time.perf_counter()
    try:
        if settings.ai_force_failure:
            raise RuntimeError("Simulated AI provider outage (AI_FORCE_FAILURE=true)")

        result = ai.analyze_request(title=request.title, description=request.description)
        duration_ms = int((time.perf_counter() - started) * 1000)
        rec = result.recommendation

        dept_id = None
        if rec.recommended_department_code:
            dept = (
                db.query(Department)
                .filter(Department.code == rec.recommended_department_code)
                .first()
            )
            if dept:
                dept_id = dept.id

        if rec.is_hr_sensitive:
            request.is_hr_sensitive = True

        analysis = AIAnalysis(
            request_id=request.id,
            provider=result.provider,
            status=AIAnalysisStatus.COMPLETED,
            confidence=Decimal(str(round(rec.confidence, 4))),
            recommended_department_id=dept_id,
            rationale=rec.rationale,
            raw_response={
                **result.raw_response,
                "is_hr_sensitive": rec.is_hr_sensitive,
            },
            idempotency_key=key,
            model_id=result.model_id,
            prompt_version=result.prompt_version,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            duration_ms=duration_ms,
            recommended_priority=rec.recommended_priority,
        )
        db.add(analysis)
        db.flush()
        db.add(
            RequestHistory(
                request_id=request.id,
                actor_id=None,
                action="ai_analysis_completed",
                from_status=request.status.value,
                to_status=request.status.value,
                details=(
                    f"provider={result.provider} model={result.model_id} "
                    f"dept={rec.recommended_department_code} confidence={rec.confidence}"
                ),
            )
        )
        apply_routing_after_analysis(db, request=request, analysis=analysis)
        db.commit()
        db.refresh(analysis)
        return analysis
    except Exception as exc:  # noqa: BLE001 — persist failure then route to review
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.exception("AI analysis failed for request %s", request_id)
        analysis = AIAnalysis(
            request_id=request.id,
            provider=getattr(ai, "name", "unknown"),
            status=AIAnalysisStatus.FAILED,
            confidence=None,
            recommended_department_id=None,
            rationale=None,
            raw_response={"error": str(exc)},
            idempotency_key=f"{key}:failed:{int(time.time())}",
            error_message=str(exc)[:2000],
            model_id=getattr(ai, "model_id", None) or getattr(ai, "name", "unknown"),
            prompt_version=None,
            input_tokens=None,
            output_tokens=None,
            duration_ms=duration_ms,
            recommended_priority=None,
        )
        db.add(analysis)
        db.flush()
        db.add(
            RequestHistory(
                request_id=request.id,
                actor_id=None,
                action="ai_analysis_failed",
                from_status=request.status.value,
                to_status=request.status.value,
                details=str(exc)[:500],
            )
        )
        apply_routing_after_analysis(db, request=request, analysis=analysis)
        db.commit()
        db.refresh(analysis)
        return analysis
