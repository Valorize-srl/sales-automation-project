"""Drop prospecting_tools table.

The /prospecting page is being slimmed down to a single Apollo Search People
tool, folded into the /leads "Arricchisci" dropdown. The prospecting_tools
metadata table (seeded by migration 019) was used by the settings UI to
toggle on/off and configure tool cards — a UI that no longer exists.

No FK references to clean up: only `apollo_search_history` is shared with
the surviving Apollo tool and it has no FK to prospecting_tools.

Revision ID: 036
"""
from alembic import op


revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS prospecting_tools CASCADE")


def downgrade() -> None:
    # Migration 019 recreates it. Not reproducing the schema here.
    pass
