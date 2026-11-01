"""Request comment thread (visible to requester + handlers)."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.assignment import Assignment, AssignmentStatus
from app.models.request import Request
from app.models.request_comment import RequestComment
from app.models.user import User
from app.modules.requests import authz


def _can_comment(db: Session, user: User, request: Request) -> bool:
    if not authz.can_view_request(db, user, request):
        return False
    if authz.can_edit_as_requester(user, request):
        return True
    if authz.is_admin(user) or authz.is_manager(user) or authz.is_reviewer(user) or authz.is_hr(user):
        return True
    active = (
        db.query(Assignment)
        .filter(
            Assignment.request_id == request.id,
            Assignment.status == AssignmentStatus.ACTIVE,
            Assignment.assignee_id == user.id,
        )
        .first()
    )
    return active is not None


def list_comments(db: Session, *, user: User, request: Request) -> list[RequestComment]:
    authz.require_view(db, user, request)
    return (
        db.query(RequestComment)
        .options(joinedload(RequestComment.author))
        .filter(RequestComment.request_id == request.id)
        .order_by(RequestComment.created_at.asc())
        .all()
    )


def add_comment(
    db: Session,
    *,
    user: User,
    request: Request,
    body: str,
) -> RequestComment:
    authz.require_view(db, user, request)
    if not _can_comment(db, user, request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot comment")
    text = body.strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty comment")
    comment = RequestComment(request_id=request.id, author_id=user.id, body=text)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment
