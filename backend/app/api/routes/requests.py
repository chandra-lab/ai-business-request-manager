"""Request management API (Phase 2)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.ai_analysis import AIAnalysis
from app.models.request import RequestPriority, RequestStatus
from app.models.user import User
from app.modules.requests import authz
from app.modules.requests.attachments import absolute_path_for, save_attachment
from app.modules.requests.service import (
    create_request,
    get_request_or_404,
    list_history,
    list_requests,
    update_request,
)
from app.modules.comments import service as comments_service
from app.schemas.requests import (
    AIAnalysisOut,
    AttachmentOut,
    CommentCreate,
    CommentOut,
    RequestCreate,
    RequestDetail,
    RequestHistoryOut,
    RequestListResponse,
    RequestSummary,
    RequestUpdate,
)

router = APIRouter(prefix="/requests", tags=["requests"])


@router.post("", response_model=RequestDetail, status_code=status.HTTP_201_CREATED)
def create_request_endpoint(
    body: RequestCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RequestDetail:
    request, created = create_request(
        db,
        user=current_user,
        body=body,
        idempotency_key=idempotency_key.strip() if idempotency_key else None,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    detail = get_request_or_404(db, request.id)
    return RequestDetail.model_validate(detail)


@router.get("", response_model=RequestListResponse)
def list_requests_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status_filter: RequestStatus | None = Query(default=None, alias="status"),
    priority: RequestPriority | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> RequestListResponse:
    items, total = list_requests(
        db,
        user=current_user,
        status_filter=status_filter,
        priority_filter=priority,
        page=page,
        page_size=page_size,
    )
    return RequestListResponse(
        items=[RequestSummary.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{request_id}", response_model=RequestDetail)
def get_request_endpoint(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RequestDetail:
    request = get_request_or_404(db, request_id)
    authz.require_view(db, current_user, request)
    return RequestDetail.model_validate(request)


@router.patch("/{request_id}", response_model=RequestDetail)
def patch_request_endpoint(
    request_id: UUID,
    body: RequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RequestDetail:
    request = get_request_or_404(db, request_id)
    updated = update_request(db, user=current_user, request=request, body=body)
    refreshed = get_request_or_404(db, updated.id)
    return RequestDetail.model_validate(refreshed)


@router.get("/{request_id}/history", response_model=list[RequestHistoryOut])
def get_history_endpoint(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RequestHistoryOut]:
    request = get_request_or_404(db, request_id)
    authz.require_view(db, current_user, request)
    # Internal status transitions are staff-only; employees use the comments thread.
    if not authz.can_view_internal_history(current_user):
        return []
    return [RequestHistoryOut.model_validate(h) for h in list_history(db, request_id)]


@router.get("/{request_id}/comments", response_model=list[CommentOut])
def list_comments_endpoint(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CommentOut]:
    request = get_request_or_404(db, request_id)
    items = comments_service.list_comments(db, user=current_user, request=request)
    out: list[CommentOut] = []
    for c in items:
        payload = CommentOut.model_validate(c)
        payload.author_name = c.author.full_name if c.author is not None else None
        out.append(payload)
    return out


@router.post(
    "/{request_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_comment_endpoint(
    request_id: UUID,
    body: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommentOut:
    request = get_request_or_404(db, request_id)
    comment = comments_service.add_comment(
        db, user=current_user, request=request, body=body.body
    )
    payload = CommentOut.model_validate(comment)
    payload.author_name = current_user.full_name
    return payload


@router.get("/{request_id}/analysis", response_model=AIAnalysisOut)
def get_analysis_endpoint(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIAnalysisOut:
    request = get_request_or_404(db, request_id)
    authz.require_view(db, current_user, request)
    from sqlalchemy.orm import joinedload

    analysis = (
        db.query(AIAnalysis)
        .options(joinedload(AIAnalysis.recommended_department))
        .filter(AIAnalysis.request_id == request_id)
        .order_by(AIAnalysis.created_at.desc())
        .first()
    )
    if analysis is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not available yet")
    dept_code = (
        analysis.recommended_department.code if analysis.recommended_department is not None else None
    )
    return AIAnalysisOut(
        id=analysis.id,
        provider=analysis.provider,
        status=analysis.status.value if hasattr(analysis.status, "value") else str(analysis.status),
        confidence=float(analysis.confidence) if analysis.confidence is not None else None,
        recommended_department_id=analysis.recommended_department_id,
        recommended_department_code=dept_code,
        recommended_priority=analysis.recommended_priority,
        rationale=analysis.rationale,
        model_id=analysis.model_id,
        prompt_version=analysis.prompt_version,
        input_tokens=analysis.input_tokens,
        output_tokens=analysis.output_tokens,
        duration_ms=analysis.duration_ms,
        created_at=analysis.created_at,
    )


@router.post(
    "/{request_id}/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment_endpoint(
    request_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttachmentOut:
    request = get_request_or_404(db, request_id)
    attachment = await save_attachment(db, user=current_user, request=request, upload=file)
    return AttachmentOut.model_validate(attachment)


@router.get("/{request_id}/attachments/{attachment_id}")
def download_attachment_endpoint(
    request_id: UUID,
    attachment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    from fastapi import HTTPException
    from app.models.attachment import Attachment

    request = get_request_or_404(db, request_id)
    authz.require_attachment_download(db, current_user, request)
    attachment = (
        db.query(Attachment)
        .filter(Attachment.id == attachment_id, Attachment.request_id == request_id)
        .first()
    )
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    path = absolute_path_for(attachment)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing on disk")
    from app.modules.audit.service import write_audit

    write_audit(
        db,
        actor_id=current_user.id,
        action="attachment.download",
        resource_type="attachment",
        resource_id=str(attachment.id),
        details=f"Downloaded attachment for request {request_id}",
        metadata={"request_id": str(request_id), "is_hr_case": authz.is_hr_case(request)},
        commit=True,
    )
    return FileResponse(
        path,
        media_type=attachment.content_type,
        filename=attachment.filename,
    )
