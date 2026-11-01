"""SSE live updates for request status / AI analysis (Phase 6)."""

from __future__ import annotations

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import SessionLocal, get_db
from app.models.ai_analysis import AIAnalysis
from app.models.request import Request as BizRequest
from app.models.user import User
from app.modules.requests import authz
from app.modules.requests.service import get_request_or_404

router = APIRouter(prefix="/requests", tags=["events"])


def _snapshot(db: Session, request_id: UUID) -> dict:
    req = db.query(BizRequest).filter(BizRequest.id == request_id).first()
    analysis = (
        db.query(AIAnalysis)
        .filter(AIAnalysis.request_id == request_id)
        .order_by(AIAnalysis.created_at.desc())
        .first()
    )
    return {
        "request_id": str(request_id),
        "status": req.status.value if req else None,
        "updated_at": req.updated_at.isoformat() if req and req.updated_at else None,
        "analysis_status": analysis.status.value if analysis else None,
        "confidence": float(analysis.confidence) if analysis and analysis.confidence is not None else None,
        "recommended_department_id": (
            str(analysis.recommended_department_id)
            if analysis and analysis.recommended_department_id
            else None
        ),
    }


@router.get("/{request_id}/events")
async def request_events(
    request_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    biz = get_request_or_404(db, request_id)
    authz.require_view(db, current_user, biz)

    async def event_gen():
        last = None
        # Initial snapshot
        session = SessionLocal()
        try:
            snap = _snapshot(session, request_id)
            last = json.dumps(snap, sort_keys=True)
            yield f"event: snapshot\ndata: {json.dumps(snap)}\n\n"
        finally:
            session.close()

        ticks = 0
        while ticks < 90:  # ~3 minutes at 2s
            if await request.is_disconnected():
                break
            await asyncio.sleep(2)
            ticks += 1
            session = SessionLocal()
            try:
                snap = _snapshot(session, request_id)
                payload = json.dumps(snap)
                key = json.dumps(snap, sort_keys=True)
                if key != last:
                    last = key
                    yield f"event: update\ndata: {payload}\n\n"
                else:
                    yield f"event: ping\ndata: {{\"ok\":true}}\n\n"
                # Stop streaming once analysis exists and status left early pipeline
                if snap.get("analysis_status") in {"completed", "failed"} and snap.get(
                    "status"
                ) not in {"submitted", "ai_processing", None}:
                    yield f"event: done\ndata: {payload}\n\n"
                    break
            finally:
                session.close()

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
