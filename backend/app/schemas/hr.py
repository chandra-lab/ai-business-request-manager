"""HR case note and access schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class HRCaseNoteCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


class HRCaseNoteOut(BaseModel):
    id: UUID
    request_id: UUID
    author_id: UUID
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class HRCaseAccessGrant(BaseModel):
    user_id: UUID


class HRCaseAccessOut(BaseModel):
    id: UUID
    request_id: UUID
    user_id: UUID
    granted_by_id: UUID | None
    granted_at: datetime
    revoked_at: datetime | None = None

    model_config = {"from_attributes": True}
