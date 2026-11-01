"""add ai analysis metrics columns

Revision ID: c8d2f3b05e21
Revises: b7c1e2a94f10
Create Date: 2026-11-01 09:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8d2f3b05e21"
down_revision: Union[str, None] = "b7c1e2a94f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_analyses", sa.Column("model_id", sa.String(length=128), nullable=True))
    op.add_column("ai_analyses", sa.Column("prompt_version", sa.String(length=64), nullable=True))
    op.add_column("ai_analyses", sa.Column("input_tokens", sa.Integer(), nullable=True))
    op.add_column("ai_analyses", sa.Column("output_tokens", sa.Integer(), nullable=True))
    op.add_column("ai_analyses", sa.Column("duration_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_analyses", "duration_ms")
    op.drop_column("ai_analyses", "output_tokens")
    op.drop_column("ai_analyses", "input_tokens")
    op.drop_column("ai_analyses", "prompt_version")
    op.drop_column("ai_analyses", "model_id")
