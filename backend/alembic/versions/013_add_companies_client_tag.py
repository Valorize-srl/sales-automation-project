"""add client_tag to companies

Revision ID: 013
Revises: 012
Create Date: 2026-02-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '013'
down_revision: Union[str, None] = '012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add client_tag column to companies table
    op.add_column('companies', sa.Column('client_tag', sa.String(length=200), nullable=True))
    # Create index for faster filtering
    op.create_index('ix_companies_client_tag', 'companies', ['client_tag'])


def downgrade() -> None:
    # Remove index and column
    op.drop_index('ix_companies_client_tag', table_name='companies')
    op.drop_column('companies', 'client_tag')
