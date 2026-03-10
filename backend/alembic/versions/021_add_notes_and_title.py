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
    # Use IF NOT EXISTS to avoid failure if columns already exist
    op.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS notes TEXT")
    op.execute("ALTER TABLE people ADD COLUMN IF NOT EXISTS title VARCHAR(255)")
    op.execute("ALTER TABLE people ADD COLUMN IF NOT EXISTS notes TEXT")


def downgrade() -> None:
    op.drop_column("people", "notes")
    op.drop_column("people", "title")
    op.drop_column("companies", "notes")
