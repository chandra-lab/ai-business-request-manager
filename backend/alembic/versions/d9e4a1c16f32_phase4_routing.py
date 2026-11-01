"""phase4 routing fields and notifications

Revision ID: d9e4a1c16f32
Revises: c8d2f3b05e21
Create Date: 2026-11-01 09:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d9e4a1c16f32"
down_revision: Union[str, None] = "c8d2f3b05e21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extend request_status enum
    op.execute("ALTER TYPE request_status ADD VALUE IF NOT EXISTS 'pending_assignment'")

    confidentiality = postgresql.ENUM(
        "standard",
        "highly_confidential",
        name="confidentiality_level",
        create_type=False,
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE confidentiality_level AS ENUM "
        "('standard', 'highly_confidential'); EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )

    op.add_column(
        "requests",
        sa.Column(
            "confidentiality",
            confidentiality,
            server_default="standard",
            nullable=False,
        ),
    )
    op.add_column(
        "requests",
        sa.Column(
            "clarification_required",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    op.add_column(
        "ai_analyses",
        sa.Column("recommended_priority", sa.String(length=32), nullable=True),
    )

    op.add_column(
        "request_review_queue",
        sa.Column(
            "clarification_required",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "request_review_queue",
        sa.Column("decision", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "request_review_queue",
        sa.Column("decision_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "request_review_queue",
        sa.Column("assigned_department_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_review_queue_assigned_department",
        "request_review_queue",
        "departments",
        ["assigned_department_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("request_id", sa.UUID(), nullable=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["request_id"], ["requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_request_id", "notifications", ["request_id"])
    op.create_index("ix_notifications_type", "notifications", ["type"])


def downgrade() -> None:
    op.drop_index("ix_notifications_type", table_name="notifications")
    op.drop_index("ix_notifications_request_id", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")

    op.drop_constraint(
        "fk_review_queue_assigned_department",
        "request_review_queue",
        type_="foreignkey",
    )
    op.drop_column("request_review_queue", "assigned_department_id")
    op.drop_column("request_review_queue", "decision_reason")
    op.drop_column("request_review_queue", "decision")
    op.drop_column("request_review_queue", "clarification_required")
    op.drop_column("ai_analyses", "recommended_priority")
    op.drop_column("requests", "clarification_required")
    op.drop_column("requests", "confidentiality")
    # Enum value pending_assignment cannot be easily removed on Postgres
