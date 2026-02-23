"""add client_tag to leads

Revision ID: 011
Revises: 010
Create Date: 2026-02-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '011'
down_revision: Union[str, None] = '010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add client_tag column to leads table
    op.add_column('leads', sa.Column('client_tag', sa.String(length=200), nullable=True))
    # Create index for faster filtering
    op.create_index('ix_leads_client_tag', 'leads', ['client_tag'])


def downgrade() -> None:
    # Remove index and column
    op.drop_index('ix_leads_client_tag', table_name='leads')
    op.drop_column('leads', 'client_tag')
