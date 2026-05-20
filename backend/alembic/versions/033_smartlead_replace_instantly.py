"""Smartlead Phase 1: additive — add email_responses.smartlead_lead_id.

First of 4 PRs replacing Instantly with Smartlead. This migration is
intentionally additive-only. The Instantly campaign data wipe + push-flag
reset is deferred to the Phase 3 migration so that the wipe happens
atomically with the provider cutover (when call sites actually switch
from instantly_service to smartlead_service).

What this adds:
  - `email_responses.smartlead_lead_id` — required by the Smartlead
    reply-to-thread API, which needs both a message_id and a lead_id to
    dispatch a reply on the original thread.

Column names like `instantly_campaign_id`, `instantly_email_id`,
`pushed_to_instantly` are intentionally NOT renamed — they will store
Smartlead values going forward, and the leads section reads these field
names. A future cleanup PR (outside the leads section) may rename them.

Revision ID: 033
"""
import sqlalchemy as sa
from alembic import op


revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_responses",
        sa.Column("smartlead_lead_id", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("email_responses", "smartlead_lead_id")
