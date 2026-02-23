"""Add company enrichment fields

Revision ID: 014
Revises: 013
Create Date: 2026-02-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add enrichment tracking fields to companies table."""
    # Add enrichment columns
    op.add_column('companies', sa.Column('generic_emails', sa.String(1000), nullable=True))
    op.add_column('companies', sa.Column('enrichment_source', sa.String(50), nullable=True))
    op.add_column('companies', sa.Column('enrichment_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('companies', sa.Column('enrichment_status', sa.String(50), nullable=True))

    # Add index for querying by enrichment status
    op.create_index('ix_companies_enrichment_status', 'companies', ['enrichment_status'])


def downgrade() -> None:
    """Remove enrichment tracking fields from companies table."""
    op.drop_index('ix_companies_enrichment_status', 'companies')
    op.drop_column('companies', 'enrichment_status')
    op.drop_column('companies', 'enrichment_date')
    op.drop_column('companies', 'enrichment_source')
    op.drop_column('companies', 'generic_emails')
