"""Request management schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.request import RequestPriority, RequestStatus


class RequestCreate(BaseModel):
    """Employees do not set priority — AI applies it after analysis.

    Sending ``priority`` is rejected (extra fields forbidden) so clients cannot
    smuggle a priority on create.
    """

    model_config = {"extra": "forbid"}

    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10, max_length=20_000)
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


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class CommentOut(BaseModel):
    id: UUID
    request_id: UUID
    author_id: UUID
    author_name: str | None = None
    body: str
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
    description_redacted: bool = False
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
