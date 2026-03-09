"""Widen generic_emails column from VARCHAR(1000) to TEXT.

Revision ID: 020
Revises: 019
"""
from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "companies",
        "generic_emails",
        existing_type=sa.String(1000),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "companies",
        "generic_emails",
        existing_type=sa.Text(),
        type_=sa.String(1000),
        existing_nullable=True,
    )
