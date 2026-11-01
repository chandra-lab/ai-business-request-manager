"""Protected HR case notes — isolated from general request comments."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.request import Request
    from app.models.user import User


class HRCaseNote(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """HR-only notes bound to a sensitive request case.

    Access control is enforced in later phases; the table exists so the
    schema boundary is present from Phase 1.
    """

    __tablename__ = "hr_case_notes"

    request_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    request: Mapped[Request] = relationship("Request", back_populates="hr_notes")
    author: Mapped[User] = relationship("User")
