"""create usage tracking tables

Revision ID: 010
Revises: 009
Create Date: 2026-02-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create apollo_search_history table
    op.create_table(
        'apollo_search_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('search_type', sa.String(length=20), nullable=False),
        sa.Column('search_query', sa.Text(), nullable=True),
        sa.Column('filters_applied', sa.JSON(), nullable=True),
        sa.Column('results_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('apollo_credits_consumed', sa.Integer(), server_default='0', nullable=False),
        sa.Column('claude_input_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('claude_output_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('cost_apollo_usd', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('cost_claude_usd', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('cost_total_usd', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('client_tag', sa.String(length=200), nullable=True),
        sa.Column('icp_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['icp_id'], ['icps.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_apollo_search_history_icp_id', 'apollo_search_history', ['icp_id'])
    op.create_index('ix_apollo_search_history_client_tag', 'apollo_search_history', ['client_tag'])
    op.create_index('ix_apollo_search_history_created_at', 'apollo_search_history', ['created_at'])

    # Create settings table
    op.create_table(
        'settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.String(length=500), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )
    op.create_index('ix_settings_key', 'settings', ['key'], unique=True)

    # Seed initial settings
    op.execute("""
        INSERT INTO settings (key, value, description)
        VALUES ('usd_eur_exchange_rate', '0.92', 'Exchange rate from USD to EUR for cost display')
    """)


def downgrade() -> None:
    # Drop indexes and tables
    op.drop_index('ix_settings_key', table_name='settings')
    op.drop_table('settings')

    op.drop_index('ix_apollo_search_history_created_at', table_name='apollo_search_history')
    op.drop_index('ix_apollo_search_history_client_tag', table_name='apollo_search_history')
    op.drop_index('ix_apollo_search_history_icp_id', table_name='apollo_search_history')
    op.drop_table('apollo_search_history')
