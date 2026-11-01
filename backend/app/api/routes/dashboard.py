"""Role dashboards (Phase 2 employee + Phase 6 role views)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.request import Request
from app.models.user import User
from app.modules.dashboard import service as dash
from app.modules.requests import authz
from app.modules.requests.service import employee_dashboard
from app.schemas.requests import EmployeeDashboardResponse, RequestSummary
from app.schemas.routing import ReviewQueueItem

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DepartmentDashboardResponse(BaseModel):
    pending_assignment_count: int
    assigned_count: int
    in_progress_count: int
    resolved_count: int
    recent: list[RequestSummary]


class ReviewDashboardResponse(BaseModel):
    open_count: int
    in_review_count: int
    items: list[ReviewQueueItem]


class HRDashboardResponse(BaseModel):
    case_count: int
    highly_confidential_count: int
    recent: list[RequestSummary]


@router.get("/employee", response_model=EmployeeDashboardResponse)
def employee_dashboard_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EmployeeDashboardResponse:
    data = employee_dashboard(db, current_user)
    return EmployeeDashboardResponse(
        open_count=data["open_count"],
        submitted_count=data["submitted_count"],
        in_progress_count=data["in_progress_count"],
        resolved_count=data["resolved_count"],
        recent=[RequestSummary.model_validate(r) for r in data["recent"]],
    )


@router.get("/department", response_model=DepartmentDashboardResponse)
def department_dashboard_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DepartmentDashboardResponse:
    if not (authz.is_manager(current_user) or authz.is_admin(current_user)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager role required")
    data = dash.department_dashboard(db, current_user)
    return DepartmentDashboardResponse(
        pending_assignment_count=data["pending_assignment_count"],
        assigned_count=data["assigned_count"],
        in_progress_count=data["in_progress_count"],
        resolved_count=data["resolved_count"],
        recent=[RequestSummary.model_validate(r) for r in data["recent"]],
    )


@router.get("/review", response_model=ReviewDashboardResponse)
def review_dashboard_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewDashboardResponse:
    if not (authz.is_reviewer(current_user) or authz.is_admin(current_user)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer role required")
    data = dash.review_dashboard(db, current_user)
    items: list[ReviewQueueItem] = []
    for item in data["items"]:
        payload = ReviewQueueItem.model_validate(item)
        req = db.query(Request).filter(Request.id == item.request_id).first()
        if req is not None:
            payload.request = RequestSummary.model_validate(req)
        items.append(payload)
    return ReviewDashboardResponse(
        open_count=data["open_count"],
        in_review_count=data["in_review_count"],
        items=items,
    )


@router.get("/hr", response_model=HRDashboardResponse)
def hr_dashboard_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HRDashboardResponse:
    if not authz.is_hr(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HR role required")
    data = dash.hr_dashboard(db, current_user)
    return HRDashboardResponse(
        case_count=data["case_count"],
        highly_confidential_count=data["highly_confidential_count"],
        recent=[RequestSummary.model_validate(r) for r in data["recent"]],
    )
