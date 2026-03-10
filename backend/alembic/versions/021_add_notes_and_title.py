"""Add notes to companies/people and title to people.

Revision ID: 021
Revises: 020
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    conn = op.get_bind()
    inspector = inspect(conn)
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    if not _has_column("companies", "notes"):
        op.add_column("companies", sa.Column("notes", sa.Text(), nullable=True))
    if not _has_column("people", "title"):
        op.add_column("people", sa.Column("title", sa.String(255), nullable=True))
    if not _has_column("people", "notes"):
        op.add_column("people", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("people", "notes")
    op.drop_column("people", "title")
    op.drop_column("companies", "notes")
