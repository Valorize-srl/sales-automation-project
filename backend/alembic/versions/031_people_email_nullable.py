"""Make people.email nullable.

People discovered via LinkedIn (Google SERP) have a profile URL but no email.
The unique index on LOWER(email) already excludes NULLs, so this is a clean
relaxation — non-null emails are still de-duplicated.

Revision ID: 031
"""
import sqlalchemy as sa
from alembic import op

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("people", "email", existing_type=sa.String(255), nullable=True)


def downgrade() -> None:
    # Backfill nulls with a placeholder so the NOT NULL constraint can be re-applied.
    op.execute("UPDATE people SET email = 'unknown-' || id || '@no-email.local' WHERE email IS NULL")
    op.alter_column("people", "email", existing_type=sa.String(255), nullable=False)
