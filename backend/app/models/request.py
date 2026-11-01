"""Business request entity."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.ai_analysis import AIAnalysis
    from app.models.assignment import Assignment
    from app.models.attachment import Attachment
    from app.models.department import Department
    from app.models.hr_case_note import HRCaseNote
    from app.models.request_history import RequestHistory
    from app.models.user import User


class RequestStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    AI_PROCESSING = "ai_processing"
    PENDING_REVIEW = "pending_review"
    PENDING_ASSIGNMENT = "pending_assignment"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class ConfidentialityLevel(StrEnum):
    STANDARD = "standard"
    HIGHLY_CONFIDENTIAL = "highly_confidential"


class RequestPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Request(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "requests"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status", values_callable=lambda x: [e.value for e in x]),
        default=RequestStatus.DRAFT,
        nullable=False,
        index=True,
    )
    priority: Mapped[RequestPriority] = mapped_column(
        Enum(
            RequestPriority,
            name="request_priority",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=RequestPriority.MEDIUM,
        nullable=False,
    )
    requester_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_hr_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confidentiality: Mapped[ConfidentialityLevel] = mapped_column(
        Enum(
            ConfidentialityLevel,
            name="confidentiality_level",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=ConfidentialityLevel.STANDARD,
        nullable=False,
    )
    clarification_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128),
        unique=True,
        nullable=True,
        index=True,
    )

    requester: Mapped[User] = relationship("User", foreign_keys=[requester_id])
    department: Mapped[Department | None] = relationship("Department")
    analyses: Mapped[list[AIAnalysis]] = relationship(
        "AIAnalysis",
        back_populates="request",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list[Assignment]] = relationship(
        "Assignment",
        back_populates="request",
        cascade="all, delete-orphan",
    )
    history: Mapped[list[RequestHistory]] = relationship(
        "RequestHistory",
        back_populates="request",
        cascade="all, delete-orphan",
    )
    attachments: Mapped[list[Attachment]] = relationship(
        "Attachment",
        back_populates="request",
        cascade="all, delete-orphan",
    )
    hr_notes: Mapped[list[HRCaseNote]] = relationship(
        "HRCaseNote",
        back_populates="request",
        cascade="all, delete-orphan",
    )
