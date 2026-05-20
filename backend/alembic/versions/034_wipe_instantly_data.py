"""Smartlead Phase 3 cutover: wipe historical Instantly campaign data.

The Instantly integration has been fully replaced by Smartlead in this
release. The user explicitly authorized wiping the legacy data (they
manage the surviving Instantly campaigns directly inside Instantly's UI;
no need for Miriade to mirror them). Companies, people, leads, lead
lists, custom fields, and all enrichment tables are intentionally
untouched.

Effects:
  1. TRUNCATE campaigns CASCADE — clears `campaigns`, and via FK cascade
     also `email_responses` and `analytics`. RESTART IDENTITY resets
     the SERIAL sequences so the first new Smartlead-created campaign
     starts at id=1.
  2. Reset push-state flags on `campaign_lead_lists` so the UI doesn't
     show stale "pushed to provider" markers from the Instantly era.
     The association rows themselves stay (they're user-curated).

This migration is intentionally NOT reversible (truncate is one-way).

Revision ID: 034
"""
from alembic import op


revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # FK CASCADE from campaigns clears email_responses + analytics.
    op.execute("TRUNCATE TABLE campaigns RESTART IDENTITY CASCADE")
    op.execute(
        "UPDATE campaign_lead_lists "
        "SET pushed_to_instantly = false, pushed_count = 0"
    )


def downgrade() -> None:
    # TRUNCATE is irreversible — no-op downgrade.
    pass
