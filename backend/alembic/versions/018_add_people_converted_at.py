"""add converted_at to people

Revision ID: 018
Revises: 017
Create Date: 2026-03-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '018'
down_revision: Union[str, None] = '017'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('people', sa.Column('converted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('people', 'converted_at')
