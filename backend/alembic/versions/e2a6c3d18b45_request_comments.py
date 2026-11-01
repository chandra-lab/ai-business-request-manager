"""add request_comments table

Revision ID: e2a6c3d18b45
Revises: d9e4a1c16f32
Create Date: 2026-11-01 16:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2a6c3d18b45"
down_revision: Union[str, None] = "d9e4a1c16f32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "request_comments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["request_id"], ["requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_request_comments_request_id", "request_comments", ["request_id"])
    op.create_index("ix_request_comments_author_id", "request_comments", ["author_id"])


def downgrade() -> None:
    op.drop_index("ix_request_comments_author_id", table_name="request_comments")
    op.drop_index("ix_request_comments_request_id", table_name="request_comments")
    op.drop_table("request_comments")
