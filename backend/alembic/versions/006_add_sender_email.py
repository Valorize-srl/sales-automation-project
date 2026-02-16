"""Add sender_email column to email_responses.

Revision ID: 006
Revises: 005
"""

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_responses",
        sa.Column("sender_email", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("email_responses", "sender_email")
