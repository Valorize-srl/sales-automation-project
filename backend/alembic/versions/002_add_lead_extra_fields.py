"""add lead extra fields

Revision ID: 002
Revises: 001
Create Date: 2026-02-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("address", sa.String(500), nullable=True))
    op.add_column("leads", sa.Column("city", sa.String(100), nullable=True))
    op.add_column("leads", sa.Column("state", sa.String(100), nullable=True))
    op.add_column("leads", sa.Column("zip_code", sa.String(20), nullable=True))
    op.add_column("leads", sa.Column("country", sa.String(100), nullable=True))
    op.add_column("leads", sa.Column("website", sa.String(500), nullable=True))
    op.add_column("leads", sa.Column("custom_fields", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "custom_fields")
    op.drop_column("leads", "website")
    op.drop_column("leads", "country")
    op.drop_column("leads", "zip_code")
    op.drop_column("leads", "state")
    op.drop_column("leads", "city")
    op.drop_column("leads", "address")
