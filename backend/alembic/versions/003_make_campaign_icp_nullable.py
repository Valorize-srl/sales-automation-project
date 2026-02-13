"""make campaign icp_id nullable

Revision ID: 003
Revises: 002
Create Date: 2026-02-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("campaigns_icp_id_fkey", "campaigns", type_="foreignkey")
    op.alter_column("campaigns", "icp_id",
                    existing_type=sa.Integer(),
                    nullable=True)
    op.create_foreign_key(
        "campaigns_icp_id_fkey", "campaigns",
        "icps", ["icp_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("campaigns_icp_id_fkey", "campaigns", type_="foreignkey")
    op.execute("UPDATE campaigns SET icp_id = (SELECT MIN(id) FROM icps) WHERE icp_id IS NULL")
    op.alter_column("campaigns", "icp_id",
                    existing_type=sa.Integer(),
                    nullable=False)
    op.create_foreign_key(
        "campaigns_icp_id_fkey", "campaigns",
        "icps", ["icp_id"], ["id"],
        ondelete="CASCADE",
    )
