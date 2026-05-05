"""Big cleanup: drop chat / ICP / scoring / bandi / AI-Agents schema.

Direction "cowork-first" — these features were retired from the in-app
experience and moved to Claude Code. This migration drops every table,
column, and FK that the removed Python code used to touch.

What it does, in order (FKs must be dropped before parent tables):
  1. Drop FK constraints + columns:
     - campaigns.icp_id
     - apollo_search_history.icp_id, apollo_search_history.session_id
     - email_responses.ai_agent_id
     - lead_lists.ai_agent_id
     - leads.icp_id
     - companies scoring columns (icp_score, priority_tier, lifecycle_stage,
       revenue_band, employee_count_band, industry_standardized,
       reason_summary, last_scored_at, scored_with_icp_id)
  2. Drop tables (children before parents):
     tool_executions, chat_messages, chat_sessions, ai_agent_campaigns,
     ai_agent_tasks, ai_agents, signal_trackings, enrichment_tasks,
     bandi, icps

Downgrade is intentionally minimal — re-creating these tables empty so a
revert at least leaves the schema valid; data is gone forever.

Revision ID: 032
"""
import sqlalchemy as sa
from alembic import op


revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def _drop_fk_if_exists(conn, table: str, fk_name_substring: str) -> None:
    """Drop any FK on `table` whose name contains the substring. Robust to
    naming variations across earlier migrations."""
    inspector = sa.inspect(conn)
    if table not in inspector.get_table_names():
        return
    for fk in inspector.get_foreign_keys(table):
        name = fk.get("name") or ""
        if fk_name_substring in name:
            op.drop_constraint(name, table, type_="foreignkey")


def _drop_column_if_exists(conn, table: str, column: str) -> None:
    inspector = sa.inspect(conn)
    if table not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns(table)}
    if column in cols:
        # Drop any FK that references this column first
        for fk in inspector.get_foreign_keys(table):
            if column in (fk.get("constrained_columns") or []):
                fk_name = fk.get("name")
                if fk_name:
                    try:
                        op.drop_constraint(fk_name, table, type_="foreignkey")
                    except Exception:
                        pass
        # Drop indexes touching this column
        for idx in inspector.get_indexes(table):
            if column in (idx.get("column_names") or []):
                try:
                    op.drop_index(idx["name"], table_name=table)
                except Exception:
                    pass
        op.drop_column(table, column)


def _drop_table_if_exists(conn, table: str) -> None:
    inspector = sa.inspect(conn)
    if table in inspector.get_table_names():
        op.drop_table(table)


def upgrade() -> None:
    conn = op.get_bind()

    # --- 1. Drop FK + columns on tables we KEEP ---
    _drop_column_if_exists(conn, "campaigns", "icp_id")
    _drop_column_if_exists(conn, "apollo_search_history", "icp_id")
    _drop_column_if_exists(conn, "apollo_search_history", "session_id")
    _drop_column_if_exists(conn, "email_responses", "ai_agent_id")
    _drop_column_if_exists(conn, "lead_lists", "ai_agent_id")
    _drop_column_if_exists(conn, "leads", "icp_id")

    # Companies — scoring columns
    for col in (
        "icp_score",
        "priority_tier",
        "lifecycle_stage",
        "revenue_band",
        "employee_count_band",
        "industry_standardized",
        "reason_summary",
        "last_scored_at",
        "scored_with_icp_id",
    ):
        _drop_column_if_exists(conn, "companies", col)

    # --- 2. Drop tables (children first) ---
    # chat / tool subsystem
    _drop_table_if_exists(conn, "tool_executions")
    _drop_table_if_exists(conn, "chat_messages")
    _drop_table_if_exists(conn, "chat_sessions")
    # ai-agents subsystem
    _drop_table_if_exists(conn, "ai_agent_campaigns")
    _drop_table_if_exists(conn, "ai_agent_tasks")
    _drop_table_if_exists(conn, "signal_trackings")
    _drop_table_if_exists(conn, "ai_agents")
    # scoring subsystem
    _drop_table_if_exists(conn, "enrichment_tasks")
    # bandi feature
    _drop_table_if_exists(conn, "bandi")
    # ICP root (last, after every dependent FK is gone)
    _drop_table_if_exists(conn, "icps")


def downgrade() -> None:
    """Re-create the dropped tables EMPTY with minimal columns so a rollback
    leaves the schema valid. Data lost in `upgrade()` is gone forever — this
    is a one-way cleanup intentionally.
    """
    op.create_table(
        "icps",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "bandi",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "ai_agents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "enrichment_tasks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.Integer, nullable=False),
        sa.Column("task_type", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("chat_sessions.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "tool_executions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("chat_sessions.id"), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "ai_agent_campaigns",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ai_agent_id", sa.Integer, sa.ForeignKey("ai_agents.id"), nullable=False),
        sa.Column("campaign_id", sa.Integer, sa.ForeignKey("campaigns.id"), nullable=False),
    )
    op.create_table(
        "signal_trackings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ai_agent_id", sa.Integer, sa.ForeignKey("ai_agents.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # Re-add the dropped columns (nullable, no constraint to re-attach FKs)
    op.add_column("companies", sa.Column("icp_score", sa.Integer, nullable=True))
    op.add_column("companies", sa.Column("priority_tier", sa.String(1), nullable=True))
    op.add_column("companies", sa.Column("lifecycle_stage", sa.String(50), nullable=True))
    op.add_column("companies", sa.Column("revenue_band", sa.String(20), nullable=True))
    op.add_column("companies", sa.Column("employee_count_band", sa.String(20), nullable=True))
    op.add_column("companies", sa.Column("industry_standardized", sa.String(255), nullable=True))
    op.add_column("companies", sa.Column("reason_summary", sa.Text, nullable=True))
    op.add_column("companies", sa.Column("last_scored_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("companies", sa.Column("scored_with_icp_id", sa.Integer, nullable=True))
    op.add_column("campaigns", sa.Column("icp_id", sa.Integer, nullable=True))
    op.add_column("apollo_search_history", sa.Column("icp_id", sa.Integer, nullable=True))
    op.add_column("apollo_search_history", sa.Column("session_id", sa.Integer, nullable=True))
    op.add_column("email_responses", sa.Column("ai_agent_id", sa.Integer, nullable=True))
    op.add_column("lead_lists", sa.Column("ai_agent_id", sa.Integer, nullable=True))
    op.add_column("leads", sa.Column("icp_id", sa.Integer, nullable=True))
