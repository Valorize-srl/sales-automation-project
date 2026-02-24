"""Add AI Agents system with lead lists and signals tracking

Revision ID: 016
Revises: 015
Create Date: 2026-02-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add AI Agents system tables and update existing models."""

    # Create ai_agents table
    op.create_table(
        'ai_agents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('client_tag', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icp_config', JSON, nullable=False),
        sa.Column('signals_config', JSON, nullable=True),
        sa.Column('knowledge_base_text', sa.Text(), nullable=True),
        sa.Column('knowledge_base_source', sa.String(20), nullable=True),
        sa.Column('knowledge_base_files', JSON, nullable=True),
        sa.Column('apollo_credits_allocated', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('apollo_credits_consumed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_credits_reset', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for ai_agents
    op.create_index('ix_ai_agents_client_tag', 'ai_agents', ['client_tag'])
    op.create_index('ix_ai_agents_is_active', 'ai_agents', ['is_active'])
    op.create_index('ix_ai_agents_created_at', 'ai_agents', ['created_at'])

    # Create lead_lists table
    op.create_table(
        'lead_lists',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ai_agent_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('filters_snapshot', JSON, nullable=True),
        sa.Column('people_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('companies_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['ai_agent_id'], ['ai_agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for lead_lists
    op.create_index('ix_lead_lists_ai_agent_id', 'lead_lists', ['ai_agent_id'])
    op.create_index('ix_lead_lists_created_at', 'lead_lists', ['created_at'])

    # Create signal_trackings table
    op.create_table(
        'signal_trackings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ai_agent_id', sa.Integer(), nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=True),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('signal_type', sa.String(50), nullable=False),
        sa.Column('signal_data', JSON, nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['ai_agent_id'], ['ai_agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['person_id'], ['people.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for signal_trackings
    op.create_index('ix_signal_trackings_ai_agent_id', 'signal_trackings', ['ai_agent_id'])
    op.create_index('ix_signal_trackings_person_id', 'signal_trackings', ['person_id'])
    op.create_index('ix_signal_trackings_company_id', 'signal_trackings', ['company_id'])
    op.create_index('ix_signal_trackings_detected_at', 'signal_trackings', ['detected_at'])
    op.create_index('ix_signal_trackings_agent_detected', 'signal_trackings', ['ai_agent_id', 'detected_at'])

    # Create ai_agent_campaigns table (join table)
    op.create_table(
        'ai_agent_campaigns',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ai_agent_id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('auto_reply_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['ai_agent_id'], ['ai_agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for ai_agent_campaigns
    op.create_index('ix_ai_agent_campaigns_ai_agent_id', 'ai_agent_campaigns', ['ai_agent_id'])
    op.create_index('ix_ai_agent_campaigns_campaign_id', 'ai_agent_campaigns', ['campaign_id'])

    # Add columns to people table
    op.add_column('people', sa.Column('list_id', sa.Integer(), nullable=True))
    op.add_column('people', sa.Column('tags', JSON, nullable=True))
    op.add_column('people', sa.Column('enriched_at', sa.DateTime(timezone=True), nullable=True))

    # Create foreign key for people.list_id
    op.create_foreign_key(
        'fk_people_list_id',
        'people',
        'lead_lists',
        ['list_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Create index for people.list_id
    op.create_index('ix_people_list_id', 'people', ['list_id'])

    # Add columns to companies table
    op.add_column('companies', sa.Column('list_id', sa.Integer(), nullable=True))
    op.add_column('companies', sa.Column('tags', JSON, nullable=True))
    op.add_column('companies', sa.Column('enriched_at', sa.DateTime(timezone=True), nullable=True))

    # Create foreign key for companies.list_id
    op.create_foreign_key(
        'fk_companies_list_id',
        'companies',
        'lead_lists',
        ['list_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Create index for companies.list_id
    op.create_index('ix_companies_list_id', 'companies', ['list_id'])

    # Add ai_agent_id column to email_responses table
    op.add_column('email_responses', sa.Column('ai_agent_id', sa.Integer(), nullable=True))

    # Create foreign key for email_responses.ai_agent_id
    op.create_foreign_key(
        'fk_email_responses_ai_agent_id',
        'email_responses',
        'ai_agents',
        ['ai_agent_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Create index for email_responses.ai_agent_id
    op.create_index('ix_email_responses_ai_agent_id', 'email_responses', ['ai_agent_id'])


def downgrade() -> None:
    """Remove AI Agents system tables and columns."""

    # Drop index and FK from email_responses
    op.drop_index('ix_email_responses_ai_agent_id', 'email_responses')
    op.drop_constraint('fk_email_responses_ai_agent_id', 'email_responses', type_='foreignkey')
    op.drop_column('email_responses', 'ai_agent_id')

    # Drop indexes, FK and columns from companies
    op.drop_index('ix_companies_list_id', 'companies')
    op.drop_constraint('fk_companies_list_id', 'companies', type_='foreignkey')
    op.drop_column('companies', 'enriched_at')
    op.drop_column('companies', 'tags')
    op.drop_column('companies', 'list_id')

    # Drop indexes, FK and columns from people
    op.drop_index('ix_people_list_id', 'people')
    op.drop_constraint('fk_people_list_id', 'people', type_='foreignkey')
    op.drop_column('people', 'enriched_at')
    op.drop_column('people', 'tags')
    op.drop_column('people', 'list_id')

    # Drop ai_agent_campaigns table
    op.drop_index('ix_ai_agent_campaigns_campaign_id', 'ai_agent_campaigns')
    op.drop_index('ix_ai_agent_campaigns_ai_agent_id', 'ai_agent_campaigns')
    op.drop_table('ai_agent_campaigns')

    # Drop signal_trackings table
    op.drop_index('ix_signal_trackings_agent_detected', 'signal_trackings')
    op.drop_index('ix_signal_trackings_detected_at', 'signal_trackings')
    op.drop_index('ix_signal_trackings_company_id', 'signal_trackings')
    op.drop_index('ix_signal_trackings_person_id', 'signal_trackings')
    op.drop_index('ix_signal_trackings_ai_agent_id', 'signal_trackings')
    op.drop_table('signal_trackings')

    # Drop lead_lists table
    op.drop_index('ix_lead_lists_created_at', 'lead_lists')
    op.drop_index('ix_lead_lists_ai_agent_id', 'lead_lists')
    op.drop_table('lead_lists')

    # Drop ai_agents table
    op.drop_index('ix_ai_agents_created_at', 'ai_agents')
    op.drop_index('ix_ai_agents_is_active', 'ai_agents')
    op.drop_index('ix_ai_agents_client_tag', 'ai_agents')
    op.drop_table('ai_agents')
