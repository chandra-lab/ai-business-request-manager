"""Schemas for review queue and manager assignment."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.request import RequestPriority
from app.schemas.requests import RequestSummary


class ReviewQueueItem(BaseModel):
    id: UUID
    request_id: UUID
    reason: str
    details: str | None
    clarification_required: bool
    status: str
    decision: str | None
    decision_reason: str | None
    assigned_department_id: UUID | None
    created_at: datetime
    request: RequestSummary | None = None

    model_config = {"from_attributes": True}


class AssignDepartmentBody(BaseModel):
    department_id: UUID
    decision_reason: str = Field(min_length=3, max_length=2000)
    final_priority: RequestPriority | None = None


class RequestInformationBody(BaseModel):
    message: str = Field(min_length=3, max_length=2000)


class AssignEmployeeBody(BaseModel):
    assignee_id: UUID
    notes: str | None = Field(default=None, max_length=2000)


class AssignmentOut(BaseModel):
    id: UUID
    request_id: UUID
    department_id: UUID
    assignee_id: UUID | None
    assigned_by_id: UUID | None
    status: str
    notes: str | None
    assigned_at: datetime

    model_config = {"from_attributes": True}


class NotificationOut(BaseModel):
    id: UUID
    type: str
    title: str
    body: str
    request_id: UUID | None
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
