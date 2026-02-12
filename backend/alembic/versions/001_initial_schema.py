"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-02-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ICPs table
    op.create_table(
        "icps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("industry", sa.String(255), nullable=True),
        sa.Column("company_size", sa.String(100), nullable=True),
        sa.Column("job_titles", sa.Text(), nullable=True),
        sa.Column("geography", sa.String(255), nullable=True),
        sa.Column("revenue_range", sa.String(100), nullable=True),
        sa.Column("keywords", sa.Text(), nullable=True),
        sa.Column("raw_input", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), server_default="draft", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Leads table
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("icp_id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("job_title", sa.String(255), nullable=True),
        sa.Column("linkedin_url", sa.String(500), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("source", sa.String(50), server_default="manual", nullable=False),
        sa.Column("verified", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["icp_id"], ["icps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leads_email", "leads", ["email"])

    # Campaigns table
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("icp_id", sa.Integer(), nullable=False),
        sa.Column("instantly_campaign_id", sa.String(255), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), server_default="draft", nullable=False),
        sa.Column("subject_lines", sa.Text(), nullable=True),
        sa.Column("email_templates", sa.Text(), nullable=True),
        sa.Column("total_sent", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_opened", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_replied", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["icp_id"], ["icps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Email responses table
    op.create_table(
        "email_responses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("message_body", sa.Text(), nullable=True),
        sa.Column("direction", sa.String(50), nullable=False),
        sa.Column("sentiment", sa.String(50), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("ai_suggested_reply", sa.Text(), nullable=True),
        sa.Column("human_approved_reply", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), server_default="pending", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["campaigns.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Analytics table
    op.create_table(
        "analytics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("emails_sent", sa.Integer(), server_default="0", nullable=False),
        sa.Column("opens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("replies", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "positive_replies", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "meetings_booked", sa.Integer(), server_default="0", nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["campaigns.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("analytics")
    op.drop_table("email_responses")
    op.drop_table("campaigns")
    op.drop_index("ix_leads_email", "leads")
    op.drop_table("leads")
    op.drop_table("icps")
