"""add request idempotency key

Revision ID: b7c1e2a94f10
Revises: 45f3289a93a3
Create Date: 2026-11-01 09:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c1e2a94f10"
down_revision: Union[str, None] = "45f3289a93a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "requests",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.create_index(
        op.f("ix_requests_idempotency_key"),
        "requests",
        ["idempotency_key"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_requests_idempotency_key",
        "requests",
        ["idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_requests_idempotency_key", "requests", type_="unique")
    op.drop_index(op.f("ix_requests_idempotency_key"), table_name="requests")
    op.drop_column("requests", "idempotency_key")
