"""Replace Instantly with Smartlead — wipe campaigns/responses, add reply context.

The Instantly integration is being fully replaced by Smartlead. Existing
Instantly campaign data is disposable (the Instantly platform retains it
independently). This migration:

  1. Adds `email_responses.smartlead_lead_id` — needed by the new
     reply-to-thread flow on Smartlead, which requires both a message_id
     and a lead_id to dispatch a reply.
  2. TRUNCATEs `campaigns` with CASCADE — clears `campaigns`,
     `email_responses`, `analytics` (any FK-dependent rows).
  3. Resets `campaign_lead_lists.pushed_to_instantly`/`pushed_count` so the
     UI no longer treats old associations as "pushed".

Column names like `instantly_campaign_id`, `instantly_email_id`,
`pushed_to_instantly` are intentionally NOT renamed in this migration —
they are reused to store Smartlead values. A future cleanup PR (outside
the leads section) may rename them.

Companies, people, leads, lead_lists, lead_list_companies, custom_fields
and all enrichment tables are intentionally untouched.

Revision ID: 033
"""
import sqlalchemy as sa
from alembic import op


revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Schema: add smartlead_lead_id for the reply-to-thread flow.
    op.add_column(
        "email_responses",
        sa.Column("smartlead_lead_id", sa.String(64), nullable=True),
    )

    # 2. Wipe campaigns + cascade. RESTART IDENTITY resets the SERIAL
    #    sequence so the first new Smartlead campaign starts at id=1.
    op.execute("TRUNCATE TABLE campaigns RESTART IDENTITY CASCADE")

    # 3. Reset push-state flags on lead-list associations. The rows
    #    themselves stay (they're a user-curated association); only the
    #    "pushed to provider" flag is cleared.
    op.execute(
        "UPDATE campaign_lead_lists "
        "SET pushed_to_instantly = false, pushed_count = 0"
    )


def downgrade() -> None:
    # The TRUNCATE is irreversible — downgrade only undoes the schema add.
    op.drop_column("email_responses", "smartlead_lead_id")
