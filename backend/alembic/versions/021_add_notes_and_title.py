"""Add notes to companies/people and title to people.

Revision ID: 021
Revises: 020
"""
from alembic import op
import sqlalchemy as sa

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("people", sa.Column("title", sa.String(255), nullable=True))
    op.add_column("people", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("people", "notes")
    op.drop_column("people", "title")
    op.drop_column("companies", "notes")
