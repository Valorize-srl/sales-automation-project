"""Add chat sessions for conversational RAG

Revision ID: 015
Revises: 014
Create Date: 2026-02-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add chat_sessions, chat_messages, and tool_executions tables."""

    # Create chat_sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_uuid', sa.String(36), nullable=False),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('icp_id', sa.Integer(), nullable=True),
        sa.Column('current_icp_draft', JSON, nullable=True),
        sa.Column('session_metadata', JSON, nullable=True),
        sa.Column('total_claude_input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_claude_output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_apollo_credits', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_cost_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('client_tag', sa.String(200), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['icp_id'], ['icps.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for chat_sessions
    op.create_index('ix_chat_sessions_session_uuid', 'chat_sessions', ['session_uuid'], unique=True)
    op.create_index('ix_chat_sessions_client_tag', 'chat_sessions', ['client_tag'])
    op.create_index('ix_chat_sessions_status_updated', 'chat_sessions', ['status', 'updated_at'])

    # Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('tool_calls', JSON, nullable=True),
        sa.Column('tool_results', JSON, nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('message_metadata', JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for chat_messages
    op.create_index('ix_chat_messages_session_id', 'chat_messages', ['session_id'])
    op.create_index('ix_chat_messages_created_at', 'chat_messages', ['created_at'])
    op.create_index('ix_chat_messages_session_created', 'chat_messages', ['session_id', 'created_at'])

    # Create tool_executions table
    op.create_table(
        'tool_executions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=True),
        sa.Column('tool_name', sa.String(50), nullable=False),
        sa.Column('tool_call_id', sa.String(100), nullable=False),
        sa.Column('tool_input', JSON, nullable=False),
        sa.Column('tool_output', JSON, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='success'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('credits_consumed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], ['chat_messages.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for tool_executions
    op.create_index('ix_tool_executions_session_id', 'tool_executions', ['session_id'])
    op.create_index('ix_tool_executions_tool_name', 'tool_executions', ['tool_name'])
    op.create_index('ix_tool_executions_session_tool', 'tool_executions', ['session_id', 'tool_name'])

    # Add session_id column to apollo_search_history
    op.add_column('apollo_search_history', sa.Column('session_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_apollo_search_history_session',
        'apollo_search_history',
        'chat_sessions',
        ['session_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """Remove chat sessions tables."""

    # Remove FK from apollo_search_history
    op.drop_constraint('fk_apollo_search_history_session', 'apollo_search_history', type_='foreignkey')
    op.drop_column('apollo_search_history', 'session_id')

    # Drop tool_executions table
    op.drop_index('ix_tool_executions_session_tool', 'tool_executions')
    op.drop_index('ix_tool_executions_tool_name', 'tool_executions')
    op.drop_index('ix_tool_executions_session_id', 'tool_executions')
    op.drop_table('tool_executions')

    # Drop chat_messages table
    op.drop_index('ix_chat_messages_session_created', 'chat_messages')
    op.drop_index('ix_chat_messages_created_at', 'chat_messages')
    op.drop_index('ix_chat_messages_session_id', 'chat_messages')
    op.drop_table('chat_messages')

    # Drop chat_sessions table
    op.drop_index('ix_chat_sessions_status_updated', 'chat_sessions')
    op.drop_index('ix_chat_sessions_client_tag', 'chat_sessions')
    op.drop_index('ix_chat_sessions_session_uuid', 'chat_sessions')
    op.drop_table('chat_sessions')
