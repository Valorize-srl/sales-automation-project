"""Add fiscal identifiers + source tracking to companies.

New columns on `companies`:
- zip_code         VARCHAR(20)  — codice postale
- vat_number       VARCHAR(32)  — partita IVA
- tax_id           VARCHAR(32)  — codice fiscale
- source_company_id VARCHAR(64) — external id from origin system (e.g. Seikoo).
                                  NULL → row was inserted manually / from a
                                  different source.

All nullable, all indexed (used in filters / dedup against external systems).

Idempotent: production already has these columns (added out-of-band) so we
use IF NOT EXISTS and skip indexes that exist.

Revision ID: 037
"""
from alembic import op


revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Postgres-only — same syntax used by the rest of this project.
    op.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS zip_code VARCHAR(20)")
    op.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS vat_number VARCHAR(32)")
    op.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS tax_id VARCHAR(32)")
    op.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS source_company_id VARCHAR(64)")

    op.execute("CREATE INDEX IF NOT EXISTS ix_companies_zip_code ON companies (zip_code)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_companies_vat_number ON companies (vat_number)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_companies_tax_id ON companies (tax_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_companies_source_company_id ON companies (source_company_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_companies_source_company_id")
    op.execute("DROP INDEX IF EXISTS ix_companies_tax_id")
    op.execute("DROP INDEX IF EXISTS ix_companies_vat_number")
    op.execute("DROP INDEX IF EXISTS ix_companies_zip_code")
    op.execute("ALTER TABLE companies DROP COLUMN IF EXISTS source_company_id")
    op.execute("ALTER TABLE companies DROP COLUMN IF EXISTS tax_id")
    op.execute("ALTER TABLE companies DROP COLUMN IF EXISTS vat_number")
    op.execute("ALTER TABLE companies DROP COLUMN IF EXISTS zip_code")
