"""Dashboard endpoints (Phase 2: employee)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.modules.requests.service import employee_dashboard
from app.schemas.requests import EmployeeDashboardResponse, RequestSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


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
