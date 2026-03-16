"""add bandi table for monitoring government grants

Revision ID: 024
Revises: 023
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '024'
down_revision: Union[str, None] = '023'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if table already exists (idempotent)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'bandi')"
    ))
    if result.scalar():
        return

    op.create_table(
        'bandi',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('source_url', sa.String(1000), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('raw_description', sa.Text(), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(50), server_default='new', nullable=False),
        sa.Column('ai_summary', sa.Text(), nullable=True),
        sa.Column('target_companies', sa.Text(), nullable=True),
        sa.Column('ateco_codes', sa.JSON(), nullable=True),
        sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('amount_min', sa.Float(), nullable=True),
        sa.Column('amount_max', sa.Float(), nullable=True),
        sa.Column('funding_type', sa.String(100), nullable=True),
        sa.Column('regions', sa.JSON(), nullable=True),
        sa.Column('sectors', sa.JSON(), nullable=True),
        sa.Column('ai_analysis_raw', sa.JSON(), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_url'),
    )
    op.create_index('ix_bandi_source', 'bandi', ['source'])
    op.create_index('ix_bandi_status', 'bandi', ['status'])
    op.create_index('ix_bandi_deadline', 'bandi', ['deadline'])
    op.create_index('ix_bandi_published_at', 'bandi', ['published_at'])


def downgrade() -> None:
    op.drop_index('ix_bandi_published_at', table_name='bandi')
    op.drop_index('ix_bandi_deadline', table_name='bandi')
    op.drop_index('ix_bandi_status', table_name='bandi')
    op.drop_index('ix_bandi_source', table_name='bandi')
    op.drop_table('bandi')
