"""Manual review queue for low-confidence or failed AI routing."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.request import Request
    from app.models.user import User


class ReviewQueueStatus(StrEnum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class RequestReviewQueue(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "request_review_queue"

    request_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    clarification_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    decision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_department_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[ReviewQueueStatus] = mapped_column(
        Enum(
            ReviewQueueStatus,
            name="review_queue_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=ReviewQueueStatus.OPEN,
        nullable=False,
        index=True,
    )
    resolved_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    request: Mapped[Request] = relationship("Request")
    resolved_by: Mapped[User | None] = relationship("User")
    assigned_department: Mapped[Department | None] = relationship("Department")
