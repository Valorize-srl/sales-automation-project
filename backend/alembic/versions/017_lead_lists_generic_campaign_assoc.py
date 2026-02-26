"""Make lead_lists.ai_agent_id nullable, add client_tag, create campaign_lead_lists

Revision ID: 017
Revises: 016
Create Date: 2026-02-26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Make lead lists generic (not tied to AI agents) and add campaign association."""

    # 1. Make lead_lists.ai_agent_id nullable
    # Drop existing FK constraint, alter column, re-create FK with SET NULL
    op.drop_constraint('lead_lists_ai_agent_id_fkey', 'lead_lists', type_='foreignkey')
    op.alter_column('lead_lists', 'ai_agent_id', nullable=True)
    op.create_foreign_key(
        'fk_lead_lists_ai_agent_id',
        'lead_lists',
        'ai_agents',
        ['ai_agent_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # 2. Add client_tag column to lead_lists
    op.add_column('lead_lists', sa.Column('client_tag', sa.String(200), nullable=True))

    # 3. Create campaign_lead_lists M2M table
    op.create_table(
        'campaign_lead_lists',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('lead_list_id', sa.Integer(), nullable=False),
        sa.Column('pushed_to_instantly', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('pushed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lead_list_id'], ['lead_lists.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index('ix_campaign_lead_lists_campaign_id', 'campaign_lead_lists', ['campaign_id'])
    op.create_index('ix_campaign_lead_lists_lead_list_id', 'campaign_lead_lists', ['lead_list_id'])


def downgrade() -> None:
    """Revert: drop campaign_lead_lists, remove client_tag, make ai_agent_id required."""

    # Drop campaign_lead_lists table
    op.drop_index('ix_campaign_lead_lists_lead_list_id', 'campaign_lead_lists')
    op.drop_index('ix_campaign_lead_lists_campaign_id', 'campaign_lead_lists')
    op.drop_table('campaign_lead_lists')

    # Remove client_tag from lead_lists
    op.drop_column('lead_lists', 'client_tag')

    # Make ai_agent_id required again
    op.drop_constraint('fk_lead_lists_ai_agent_id', 'lead_lists', type_='foreignkey')
    op.alter_column('lead_lists', 'ai_agent_id', nullable=False)
    op.create_foreign_key(
        'lead_lists_ai_agent_id_fkey',
        'lead_lists',
        'ai_agents',
        ['ai_agent_id'],
        ['id'],
        ondelete='CASCADE'
    )
