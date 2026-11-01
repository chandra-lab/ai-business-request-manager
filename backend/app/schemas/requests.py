"""Request management schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.request import RequestPriority, RequestStatus


class RequestCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10, max_length=20_000)
    priority: RequestPriority = RequestPriority.MEDIUM
    submit: bool = True
    is_hr_sensitive: bool = False


class RequestUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, min_length=10, max_length=20_000)
    priority: RequestPriority | None = None
    status: RequestStatus | None = None
    is_hr_sensitive: bool | None = None


class AttachmentOut(BaseModel):
    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}


class RequestHistoryOut(BaseModel):
    id: UUID
    action: str
    from_status: str | None
    to_status: str | None
    details: str | None
    actor_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RequestSummary(BaseModel):
    id: UUID
    title: str
    status: RequestStatus
    priority: RequestPriority
    requester_id: UUID
    department_id: UUID | None
    is_hr_sensitive: bool
    confidentiality: str | None = None
    clarification_required: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RequestDetail(RequestSummary):
    description: str
    attachments: list[AttachmentOut] = []


class RequestListResponse(BaseModel):
    items: list[RequestSummary]
    total: int
    page: int
    page_size: int


class AIAnalysisOut(BaseModel):
    id: UUID
    provider: str
    status: str
    confidence: float | None
    recommended_department_id: UUID | None
    recommended_department_code: str | None = None
    recommended_priority: str | None = None
    rationale: str | None
    model_id: str | None = None
    prompt_version: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    duration_ms: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EmployeeDashboardResponse(BaseModel):
    open_count: int
    submitted_count: int
    in_progress_count: int
    resolved_count: int
    recent: list[RequestSummary]
