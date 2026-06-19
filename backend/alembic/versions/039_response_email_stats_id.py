"""Add smartlead_message_stats_id to email_responses.

The Smartlead reply-email-thread endpoint requires `email_stats_id` to
identify the original message AND to pick the correct sender account.
Without it, the Send button on /responses always 400s with "No Smartlead
lead id…" (the user-facing symptom: "click Send, nothing happens").

Webhook payload exposes this as `stats_id`. We persist it here and the
webhook handler is updated in the same PR to populate it on every new
EMAIL_REPLY.

Idempotent (IF NOT EXISTS) so this works on instances that may already
have the column from a previous attempt.

Revision ID: 039
"""
from alembic import op


revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE email_responses "
        "ADD COLUMN IF NOT EXISTS smartlead_message_stats_id VARCHAR(64)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_email_responses_smartlead_message_stats_id "
        "ON email_responses (smartlead_message_stats_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_email_responses_smartlead_message_stats_id")
    op.execute(
        "ALTER TABLE email_responses DROP COLUMN IF EXISTS smartlead_message_stats_id"
    )
