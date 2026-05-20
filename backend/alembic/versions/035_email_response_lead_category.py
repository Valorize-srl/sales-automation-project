"""Add email_responses.lead_category for Smartlead category labels.

The Smartlead webhook delivers a `lead_category` field (e.g. "Interested",
"Meeting Request", "Out Of Office", "Wrong Person", "Information Request",
"Do Not Contact", "Not Interested", "Sender Originated Bounce",
"Uncategorizable by Ai"). We already map it onto our 4-bucket Sentiment
enum for filtering/stats, but the original label is more informative —
this column stores it so the /responses UI can show it as a richer badge.

Additive only, no data destruction. Existing rows keep NULL.

Revision ID: 035
"""
import sqlalchemy as sa
from alembic import op


revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_responses",
        sa.Column("lead_category", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("email_responses", "lead_category")
