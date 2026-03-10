"""Add indexes for pagination and import performance.

Revision ID: 022
Revises: 021
Create Date: 2026-03-10

"""
from typing import Sequence, Union

from alembic import op

revision: str = '022'
down_revision: Union[str, None] = '021'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS ix_companies_industry ON companies (industry)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_companies_client_tag ON companies (client_tag)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_companies_name_lower ON companies (LOWER(name))")
    op.execute("CREATE INDEX IF NOT EXISTS ix_people_industry ON people (industry)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_people_client_tag ON people (client_tag)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_people_email_lower ON people (LOWER(email))")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_companies_industry")
    op.execute("DROP INDEX IF EXISTS ix_companies_client_tag")
    op.execute("DROP INDEX IF EXISTS ix_companies_name_lower")
    op.execute("DROP INDEX IF EXISTS ix_people_industry")
    op.execute("DROP INDEX IF EXISTS ix_people_client_tag")
    op.execute("DROP INDEX IF EXISTS ix_people_email_lower")
