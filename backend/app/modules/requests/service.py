"""Request create / list / update / history business logic."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.outbox_message import OutboxMessage, OutboxStatus
from app.models.request import Request, RequestPriority, RequestStatus
from app.models.request_history import RequestHistory
from app.models.user import User
from app.modules.requests import authz
from app.modules.requests.lifecycle import assert_transition
from app.schemas.requests import RequestCreate, RequestUpdate


def _add_history(
    db: Session,
    *,
    request: Request,
    actor: User | None,
    action: str,
    from_status: str | None,
    to_status: str | None,
    details: str | None = None,
) -> None:
    db.add(
        RequestHistory(
            request_id=request.id,
            actor_id=actor.id if actor else None,
            action=action,
            from_status=from_status,
            to_status=to_status,
            details=details,
        )
    )


def _enqueue_submitted_outbox(db: Session, request: Request) -> None:
    """Transactional outbox stub for Phase 3 AI processing."""
    db.add(
        OutboxMessage(
            aggregate_type="request",
            aggregate_id=request.id,
            event_type="request.submitted",
            payload={
                "request_id": str(request.id),
                "title": request.title,
                "requester_id": str(request.requester_id),
            },
            status=OutboxStatus.PENDING,
            idempotency_key=f"request.submitted:{request.id}",
        )
    )


def create_request(
    db: Session,
    *,
    user: User,
    body: RequestCreate,
    idempotency_key: str | None,
) -> tuple[Request, bool]:
    """Create a request. Returns (request, created_new)."""
    if idempotency_key:
        existing = (
            db.query(Request)
            .filter(Request.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            if existing.requester_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency key already used",
                )
            return existing, False

    initial = RequestStatus.SUBMITTED if body.submit else RequestStatus.DRAFT
    request = Request(
        title=body.title.strip(),
        description=body.description.strip(),
        priority=body.priority,
        status=initial,
        requester_id=user.id,
        department_id=None,  # assigned by routing in Phase 4
        is_hr_sensitive=body.is_hr_sensitive,
        idempotency_key=idempotency_key,
    )
    db.add(request)
    db.flush()

    _add_history(
        db,
        request=request,
        actor=user,
        action="created",
        from_status=None,
        to_status=initial.value,
        details="Request created" + (" and submitted" if body.submit else " as draft"),
    )
    if initial == RequestStatus.SUBMITTED:
        _enqueue_submitted_outbox(db, request)

    db.commit()
    db.refresh(request)
    return request, True


def get_request_or_404(db: Session, request_id: UUID) -> Request:
    request = (
        db.query(Request)
        .options(joinedload(Request.attachments))
        .filter(Request.id == request_id)
        .first()
    )
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return request


def list_requests(
    db: Session,
    *,
    user: User,
    status_filter: RequestStatus | None,
    priority_filter: RequestPriority | None,
    page: int,
    page_size: int,
) -> tuple[list[Request], int]:
    query = db.query(Request)
    query = authz.apply_list_scope(query, user, db)
    if status_filter is not None:
        query = query.filter(Request.status == status_filter)
    if priority_filter is not None:
        query = query.filter(Request.priority == priority_filter)

    total = query.with_entities(func.count(Request.id)).scalar() or 0
    items = (
        query.order_by(Request.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, int(total)


def update_request(
    db: Session,
    *,
    user: User,
    request: Request,
    body: RequestUpdate,
) -> Request:
    authz.require_view(user, request)

    # Field edits: requester only, and only while draft (or description clarify when submitted)
    fields_changing = any(
        v is not None for v in (body.title, body.description, body.priority, body.is_hr_sensitive)
    )
    if fields_changing:
        if not authz.can_edit_as_requester(user, request):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
        if request.status == RequestStatus.DRAFT:
            if body.title is not None:
                request.title = body.title.strip()
            if body.description is not None:
                request.description = body.description.strip()
            if body.priority is not None:
                request.priority = body.priority
            if body.is_hr_sensitive is not None:
                request.is_hr_sensitive = body.is_hr_sensitive
        elif request.status == RequestStatus.SUBMITTED and body.description is not None:
            # Narrow clarification only
            if body.title is not None or body.priority is not None or body.is_hr_sensitive is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only description clarification is allowed after submit",
                )
            request.description = body.description.strip()
            _add_history(
                db,
                request=request,
                actor=user,
                action="clarified",
                from_status=request.status.value,
                to_status=request.status.value,
                details="Requester clarified description",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot edit fields in status {request.status.value}",
            )

    if body.status is not None and body.status != request.status:
        _apply_status_change(db, user=user, request=request, target=body.status)

    db.commit()
    db.refresh(request)
    return request


def _apply_status_change(
    db: Session,
    *,
    user: User,
    request: Request,
    target: RequestStatus,
) -> None:
    try:
        assert_transition(request.status, target)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Phase 2 allowed status updates by role
    if target == RequestStatus.SUBMITTED:
        if not authz.can_edit_as_requester(user, request):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
        if request.status != RequestStatus.DRAFT:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only drafts can be submitted")
    elif target == RequestStatus.CANCELLED:
        if not (
            authz.can_edit_as_requester(user, request)
            or authz.is_admin(user)
            or (
                authz.is_manager(user)
                and user.department_id
                and request.department_id == user.department_id
            )
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
        if request.status in {RequestStatus.CLOSED, RequestStatus.CANCELLED}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already terminal")
    elif target in {RequestStatus.IN_PROGRESS, RequestStatus.RESOLVED, RequestStatus.CLOSED}:
        # Narrow manager/admin progress — full assignment UX is Phase 4
        if not (
            authz.is_admin(user)
            or (
                authz.is_manager(user)
                and user.department_id
                and request.department_id == user.department_id
            )
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    elif target == RequestStatus.AI_PROCESSING:
        # Reserved for Phase 3 workers / admin bootstrap
        if not authz.is_admin(user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Status change to {target.value} is not available in Phase 2",
        )

    previous = request.status
    request.status = target
    _add_history(
        db,
        request=request,
        actor=user,
        action="status_changed",
        from_status=previous.value,
        to_status=target.value,
    )
    if target == RequestStatus.SUBMITTED:
        _enqueue_submitted_outbox(db, request)


def list_history(db: Session, request_id: UUID) -> list[RequestHistory]:
    return (
        db.query(RequestHistory)
        .filter(RequestHistory.request_id == request_id)
        .order_by(RequestHistory.created_at.asc())
        .all()
    )


def employee_dashboard(db: Session, user: User) -> dict:
    base = db.query(Request).filter(Request.requester_id == user.id)
    open_statuses = [
        RequestStatus.DRAFT,
        RequestStatus.SUBMITTED,
        RequestStatus.AI_PROCESSING,
        RequestStatus.PENDING_REVIEW,
        RequestStatus.ASSIGNED,
        RequestStatus.IN_PROGRESS,
    ]

    def count_status(*statuses: RequestStatus) -> int:
        return (
            db.query(func.count(Request.id))
            .filter(Request.requester_id == user.id, Request.status.in_(statuses))
            .scalar()
            or 0
        )

    recent = (
        base.order_by(Request.updated_at.desc()).limit(10).all()
    )
    return {
        "open_count": count_status(*open_statuses),
        "submitted_count": count_status(
            RequestStatus.SUBMITTED,
            RequestStatus.AI_PROCESSING,
            RequestStatus.PENDING_REVIEW,
        ),
        "in_progress_count": count_status(RequestStatus.ASSIGNED, RequestStatus.IN_PROGRESS),
        "resolved_count": count_status(RequestStatus.RESOLVED, RequestStatus.CLOSED),
        "recent": recent,
    }
