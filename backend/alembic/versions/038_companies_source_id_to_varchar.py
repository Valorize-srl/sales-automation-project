"""Coerce companies.source_company_id to VARCHAR(64).

Production DB had `source_company_id` added out-of-band as UUID. Our model
declares it as String(64); SQLAlchemy returns a `uuid.UUID` instance which
Pydantic v2 then rejects with `string_type`. Symptom: every GET /companies
that touched a row with a populated id failed 500.

Convert in place. PostgreSQL can cast uuid → text losslessly; rows without
an id stay NULL. Same trick used for any of the other three columns that
might also have been created with an unexpected type.

Revision ID: 038
"""
from alembic import op


revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Cast → text first (handles uuid, int, etc.), then size-cap. NULL-safe.
    op.execute(
        "ALTER TABLE companies "
        "ALTER COLUMN source_company_id TYPE VARCHAR(64) "
        "USING source_company_id::text"
    )
    op.execute(
        "ALTER TABLE companies "
        "ALTER COLUMN zip_code TYPE VARCHAR(20) "
        "USING zip_code::text"
    )
    op.execute(
        "ALTER TABLE companies "
        "ALTER COLUMN vat_number TYPE VARCHAR(32) "
        "USING vat_number::text"
    )
    op.execute(
        "ALTER TABLE companies "
        "ALTER COLUMN tax_id TYPE VARCHAR(32) "
        "USING tax_id::text"
    )


def downgrade() -> None:
    # No-op: text → previous types would be lossy / unknown.
    pass
