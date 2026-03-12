"""add ai_agent_id to chat_sessions

Revision ID: 023
Revises: 022
Create Date: 2026-03-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '023'
down_revision: Union[str, None] = '022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if column already exists (idempotent)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT FROM information_schema.columns "
        "WHERE table_name = 'chat_sessions' AND column_name = 'ai_agent_id')"
    ))
    if result.scalar():
        return

    op.add_column(
        'chat_sessions',
        sa.Column('ai_agent_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_chat_sessions_ai_agent_id',
        'chat_sessions', 'ai_agents',
        ['ai_agent_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_chat_sessions_ai_agent_id', 'chat_sessions', ['ai_agent_id'])


def downgrade() -> None:
    op.drop_index('ix_chat_sessions_ai_agent_id', table_name='chat_sessions')
    op.drop_constraint('fk_chat_sessions_ai_agent_id', 'chat_sessions', type_='foreignkey')
    op.drop_column('chat_sessions', 'ai_agent_id')
