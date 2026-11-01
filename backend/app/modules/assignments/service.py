"""Manager individual assignment / reassignment (Phase 4)."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assignment import Assignment, AssignmentStatus
from app.models.request import Request, RequestStatus
from app.models.request_history import RequestHistory
from app.models.user import User
from app.modules.notifications.service import notify_user
from app.modules.requests import authz
from app.modules.requests.lifecycle import assert_transition


def _active_assignment(db: Session, request_id: UUID) -> Assignment | None:
    return (
        db.query(Assignment)
        .filter(
            Assignment.request_id == request_id,
            Assignment.status == AssignmentStatus.ACTIVE,
        )
        .first()
    )


def assign_employee(
    db: Session,
    *,
    request: Request,
    manager: User,
    assignee_id: UUID,
    notes: str | None = None,
) -> Assignment:
    if not (
        authz.is_admin(manager)
        or (
            authz.is_manager(manager)
            and manager.department_id
            and request.department_id == manager.department_id
        )
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    if request.status not in {
        RequestStatus.PENDING_ASSIGNMENT,
        RequestStatus.ASSIGNED,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot assign in status {request.status.value}",
        )

    assignee = db.query(User).filter(User.id == assignee_id, User.is_active.is_(True)).first()
    if assignee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found")
    if request.department_id and assignee.department_id != request.department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignee must belong to the request department",
        )

    active = _active_assignment(db, request.id)
    if active and active.assignee_id == assignee_id:
        # Idempotent: same active assignee
        return active

    if active:
        active.status = AssignmentStatus.REASSIGNED

    if request.status == RequestStatus.PENDING_ASSIGNMENT:
        assert_transition(request.status, RequestStatus.ASSIGNED)
        previous = request.status
        request.status = RequestStatus.ASSIGNED
        db.add(
            RequestHistory(
                request_id=request.id,
                actor_id=manager.id,
                action="status_changed",
                from_status=previous.value,
                to_status=request.status.value,
                details="Manager assigned individual",
            )
        )

    assignment = Assignment(
        request_id=request.id,
        department_id=request.department_id or manager.department_id,
        assignee_id=assignee_id,
        assigned_by_id=manager.id,
        status=AssignmentStatus.ACTIVE,
        notes=notes,
    )
    if assignment.department_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request has no department for assignment",
        )

    db.add(assignment)
    db.add(
        RequestHistory(
            request_id=request.id,
            actor_id=manager.id,
            action="assigned_employee" if not active else "reassigned_employee",
            from_status=request.status.value,
            to_status=request.status.value,
            details=f"assignee={assignee_id}",
        )
    )
    notify_user(
        db,
        user_id=assignee_id,
        request_id=request.id,
        type="request_assigned",
        title="You were assigned a request",
        body=f"You have been assigned: {request.title}",
    )
    db.commit()
    db.refresh(assignment)
    return assignment


def list_manager_queue(db: Session, manager: User) -> list[Request]:
    if authz.is_admin(manager):
        return (
            db.query(Request)
            .filter(Request.status == RequestStatus.PENDING_ASSIGNMENT)
            .order_by(Request.created_at.desc())
            .all()
        )
    if not authz.is_manager(manager) or not manager.department_id:
        return []
    return (
        db.query(Request)
        .filter(
            Request.status == RequestStatus.PENDING_ASSIGNMENT,
            Request.department_id == manager.department_id,
        )
        .order_by(Request.created_at.desc())
        .all()
    )
