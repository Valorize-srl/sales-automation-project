"""Add instantly_email_id, from_email, thread_id, subject to email_responses; make lead_id nullable.

Revision ID: 004
Revises: 003
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("email_responses", sa.Column("instantly_email_id", sa.String(255), nullable=True))
    op.add_column("email_responses", sa.Column("from_email", sa.String(255), nullable=True))
    op.add_column("email_responses", sa.Column("thread_id", sa.String(255), nullable=True))
    op.add_column("email_responses", sa.Column("subject", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_email_responses_instantly_email_id", "email_responses", ["instantly_email_id"])

    # Make lead_id nullable
    op.drop_constraint("email_responses_lead_id_fkey", "email_responses", type_="foreignkey")
    op.alter_column("email_responses", "lead_id", existing_type=sa.Integer(), nullable=True)
    op.create_foreign_key(
        "email_responses_lead_id_fkey",
        "email_responses",
        "leads",
        ["lead_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("email_responses_lead_id_fkey", "email_responses", type_="foreignkey")
    op.alter_column("email_responses", "lead_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        "email_responses_lead_id_fkey",
        "email_responses",
        "leads",
        ["lead_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("uq_email_responses_instantly_email_id", "email_responses", type_="unique")
    op.drop_column("email_responses", "subject")
    op.drop_column("email_responses", "thread_id")
    op.drop_column("email_responses", "from_email")
    op.drop_column("email_responses", "instantly_email_id")
