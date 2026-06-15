"""No-op placeholder for source_company_id type coercion.

Original plan was to ALTER COLUMN companies.source_company_id TYPE VARCHAR(64)
because prod added it out-of-band as UUID. Pydantic v2 was 500'ing on GET
/companies because uuid.UUID isn't accepted for `Optional[str]`.

Problem: companies has ~5M rows. ALTER COLUMN TYPE rewrites the entire
table; Railway killed the deploy after a few minutes of locked DDL.

Resolution moved to the application layer:
- CompanyResponse adds a field_validator that stringifies the four new
  columns before Pydantic touches them. Reads work whether the underlying
  column is uuid or varchar.
- Writes go through Pydantic CompanyCreate/Update which accept str; for
  the UUID-typed column Postgres auto-casts on INSERT iff the supplied
  text is valid UUID format. Manual inserts that need a non-UUID id will
  hit a clean ProgrammingError at POST time instead of a silent 500
  later — acceptable for now.

This file exists only so deployed instances that already advanced their
alembic_version past 037 don't get stuck.

Revision ID: 038
"""
from alembic import op  # noqa: F401  (kept for symmetry; unused)


revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
