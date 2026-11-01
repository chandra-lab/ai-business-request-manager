"""add department manager_user_id

Revision ID: f3b7d4e29c56
Revises: e2a6c3d18b45
Create Date: 2026-11-01 11:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3b7d4e29c56"
down_revision: Union[str, None] = "e2a6c3d18b45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("departments", sa.Column("manager_user_id", sa.UUID(), nullable=True))
    op.create_index("ix_departments_manager_user_id", "departments", ["manager_user_id"])
    op.create_foreign_key(
        "fk_departments_manager_user",
        "departments",
        "users",
        ["manager_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_departments_manager_user", "departments", type_="foreignkey")
    op.drop_index("ix_departments_manager_user_id", table_name="departments")
    op.drop_column("departments", "manager_user_id")
