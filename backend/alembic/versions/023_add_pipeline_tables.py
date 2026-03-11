"""Add pipeline_runs and pipeline_leads tables for waterfall pipeline.

Revision ID: 023
Revises: 022
Create Date: 2026-03-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision: str = '023'
down_revision: Union[str, None] = '022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- pipeline_runs ---
    op.create_table(
        'pipeline_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.String(36), nullable=False),
        sa.Column('client_tag', sa.String(100), nullable=False),
        sa.Column('ai_agent_id', sa.Integer(), nullable=True),
        sa.Column('icp_snapshot', JSON, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('current_step', sa.Integer(), nullable=False, server_default='0'),
        # Step counters
        sa.Column('leads_raw_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('leads_filtered_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('leads_with_dm_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('leads_with_email_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('leads_verified_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('leads_scored_count', sa.Integer(), nullable=False, server_default='0'),
        # Score breakdown
        sa.Column('leads_score_a', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('leads_score_b', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('leads_score_c', sa.Integer(), nullable=False, server_default='0'),
        # Cost tracking
        sa.Column('cost_scraping_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('cost_linkedin_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('cost_email_finding_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('cost_zerobounce_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('cost_signals_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('cost_claude_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('cost_total_usd', sa.Float(), nullable=False, server_default='0.0'),
        # Timestamps
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['ai_agent_id'], ['ai_agents.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pipeline_runs_run_id', 'pipeline_runs', ['run_id'], unique=True)
    op.create_index('ix_pipeline_runs_client_tag', 'pipeline_runs', ['client_tag'])
    op.create_index('ix_pipeline_runs_status', 'pipeline_runs', ['status'])
    op.create_index('ix_pipeline_runs_ai_agent_id', 'pipeline_runs', ['ai_agent_id'])

    # --- pipeline_leads ---
    op.create_table(
        'pipeline_leads',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('pipeline_run_id', sa.Integer(), nullable=False),
        # Italian company registry
        sa.Column('ragione_sociale', sa.String(500), nullable=True),
        sa.Column('partita_iva', sa.String(20), nullable=True),
        sa.Column('codice_ateco', sa.String(20), nullable=True),
        sa.Column('forma_giuridica', sa.String(100), nullable=True),
        sa.Column('fatturato_range', sa.String(100), nullable=True),
        sa.Column('dipendenti_range', sa.String(100), nullable=True),
        sa.Column('indirizzo', sa.String(500), nullable=True),
        sa.Column('provincia', sa.String(10), nullable=True),
        sa.Column('anno_costituzione', sa.Integer(), nullable=True),
        sa.Column('sito_web', sa.String(500), nullable=True),
        sa.Column('source_portal', sa.String(100), nullable=True),
        # Pipeline status
        sa.Column('pipeline_status', sa.String(30), nullable=False, server_default='raw'),
        # LinkedIn company
        sa.Column('linkedin_company_url', sa.String(500), nullable=True),
        sa.Column('linkedin_industry', sa.String(255), nullable=True),
        sa.Column('linkedin_employees_count', sa.Integer(), nullable=True),
        sa.Column('linkedin_followers', sa.Integer(), nullable=True),
        sa.Column('linkedin_status', sa.String(50), nullable=True),
        # Decision maker
        sa.Column('dm_first_name', sa.String(100), nullable=True),
        sa.Column('dm_last_name', sa.String(100), nullable=True),
        sa.Column('dm_job_title', sa.String(255), nullable=True),
        sa.Column('dm_linkedin_url', sa.String(500), nullable=True),
        sa.Column('dm_headline', sa.String(500), nullable=True),
        sa.Column('dm_found', sa.Boolean(), nullable=True),
        # Email
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('email_type', sa.String(30), nullable=True),
        sa.Column('email_confidence', sa.Float(), nullable=True),
        sa.Column('email_source', sa.String(50), nullable=True),
        sa.Column('email_catchall', sa.Boolean(), nullable=True),
        sa.Column('email_unknown', sa.Boolean(), nullable=True),
        # Signals + Scoring
        sa.Column('signals_json', JSON, nullable=True),
        sa.Column('icp_score', sa.String(5), nullable=True),
        sa.Column('score_reason', sa.Text(), nullable=True),
        sa.Column('approach_angle', sa.Text(), nullable=True),
        sa.Column('first_line_email', sa.Text(), nullable=True),
        sa.Column('relevant_products', JSON, nullable=True),
        # Flags
        sa.Column('no_website', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('exclude_flag', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('exclude_reason', sa.String(255), nullable=True),
        # Timestamps + tenancy
        sa.Column('pipeline_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pipeline_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('client_tag', sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['pipeline_run_id'], ['pipeline_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pipeline_leads_run_id', 'pipeline_leads', ['pipeline_run_id'])
    op.create_index('ix_pipeline_leads_status', 'pipeline_leads', ['pipeline_status'])
    op.create_index('ix_pipeline_leads_client_tag', 'pipeline_leads', ['client_tag'])
    op.create_index('ix_pipeline_leads_partita_iva', 'pipeline_leads', ['partita_iva'])
    op.create_index('ix_pipeline_leads_icp_score', 'pipeline_leads', ['icp_score'])
    op.create_index('ix_pipeline_leads_email', 'pipeline_leads', ['email'])
    op.create_index('ix_pipeline_leads_run_status', 'pipeline_leads', ['pipeline_run_id', 'pipeline_status'])

    # --- ai_agents: add icp_json ---
    op.add_column('ai_agents', sa.Column('icp_json', JSON, nullable=True))


def downgrade() -> None:
    op.drop_column('ai_agents', 'icp_json')
    op.drop_table('pipeline_leads')
    op.drop_table('pipeline_runs')
