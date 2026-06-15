"""Add fiscal identifiers + source tracking to companies.

New columns on `companies`:
- zip_code         VARCHAR(20)  — codice postale
- vat_number       VARCHAR(32)  — partita IVA
- tax_id           VARCHAR(32)  — codice fiscale
- source_company_id VARCHAR(64) — external id from origin system (e.g. Seikoo).
                                  NULL → row was inserted manually / from a
                                  different source.

All nullable, all indexed (used in filters / dedup against external systems).

Revision ID: 037
"""
from alembic import op
import sqlalchemy as sa


revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("zip_code", sa.String(20), nullable=True))
    op.add_column("companies", sa.Column("vat_number", sa.String(32), nullable=True))
    op.add_column("companies", sa.Column("tax_id", sa.String(32), nullable=True))
    op.add_column("companies", sa.Column("source_company_id", sa.String(64), nullable=True))

    op.create_index("ix_companies_zip_code", "companies", ["zip_code"])
    op.create_index("ix_companies_vat_number", "companies", ["vat_number"])
    op.create_index("ix_companies_tax_id", "companies", ["tax_id"])
    op.create_index("ix_companies_source_company_id", "companies", ["source_company_id"])


def downgrade() -> None:
    op.drop_index("ix_companies_source_company_id", table_name="companies")
    op.drop_index("ix_companies_tax_id", table_name="companies")
    op.drop_index("ix_companies_vat_number", table_name="companies")
    op.drop_index("ix_companies_zip_code", table_name="companies")
    op.drop_column("companies", "source_company_id")
    op.drop_column("companies", "tax_id")
    op.drop_column("companies", "vat_number")
    op.drop_column("companies", "zip_code")
