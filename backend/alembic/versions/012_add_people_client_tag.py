"""add client_tag to people

Revision ID: 012
Revises: 011
Create Date: 2026-02-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '012'
down_revision: Union[str, None] = '011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add client_tag column to people table
    op.add_column('people', sa.Column('client_tag', sa.String(length=200), nullable=True))
    # Create index for faster filtering
    op.create_index('ix_people_client_tag', 'people', ['client_tag'])


def downgrade() -> None:
    # Remove index and column
    op.drop_index('ix_people_client_tag', table_name='people')
    op.drop_column('people', 'client_tag')
