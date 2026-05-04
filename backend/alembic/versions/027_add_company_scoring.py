"""Add ICP-based scoring fields to companies + enrichment_tasks table.

Revision ID: 027
"""
import sqlalchemy as sa
from alembic import op

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # --- 1. Add scoring columns to companies (idempotent) ---
    if "companies" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("companies")}
        new_cols = [
            ("icp_score", sa.Integer(), None),
            ("priority_tier", sa.String(1), None),  # 'A' | 'B' | 'C'
            ("lifecycle_stage", sa.String(50), "new"),
            ("revenue_band", sa.String(20), None),
            ("employee_count_band", sa.String(20), None),
            ("industry_standardized", sa.String(255), None),
            ("reason_summary", sa.Text(), None),
            ("last_scored_at", sa.DateTime(timezone=True), None),
            ("scored_with_icp_id", sa.Integer(), None),
        ]
        for name, col_type, server_default in new_cols:
            if name in existing_cols:
                continue
            kwargs = {"nullable": True}
            if server_default is not None:
                kwargs["server_default"] = server_default
            op.add_column("companies", sa.Column(name, col_type, **kwargs))

        # FK on scored_with_icp_id (only if both columns/tables exist)
        existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("companies")}
        if (
            "icps" in inspector.get_table_names()
            and "scored_with_icp_id" not in {c["name"] for c in inspector.get_columns("companies")} | {n for n, _, _ in new_cols}
        ):
            pass  # column not present yet (shouldn't happen given the loop above)
        if "fk_companies_scored_with_icp" not in existing_fks and "icps" in inspector.get_table_names():
            try:
                op.create_foreign_key(
                    "fk_companies_scored_with_icp",
                    "companies",
                    "icps",
                    ["scored_with_icp_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            except Exception:
                pass

        # Helpful indexes
        existing_idx = {i["name"] for i in inspector.get_indexes("companies")}
        if "ix_companies_priority_tier" not in existing_idx:
            op.create_index("ix_companies_priority_tier", "companies", ["priority_tier"])
        if "ix_companies_lifecycle_stage" not in existing_idx:
            op.create_index("ix_companies_lifecycle_stage", "companies", ["lifecycle_stage"])

    # --- 2. Create enrichment_tasks table ---
    if "enrichment_tasks" not in inspector.get_table_names():
        op.create_table(
            "enrichment_tasks",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("target_type", sa.String(20), nullable=False),  # 'account' | 'person'
            sa.Column("target_id", sa.Integer, nullable=False),
            sa.Column("task_type", sa.String(50), nullable=False),
            sa.Column("priority", sa.Integer, nullable=False, server_default="3"),
            sa.Column("reason", sa.Text, nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("created_by_icp_id", sa.Integer, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("notes", sa.Text, nullable=True),
        )
        op.create_index("ix_enrichment_tasks_target", "enrichment_tasks", ["target_type", "target_id"])
        op.create_index("ix_enrichment_tasks_status", "enrichment_tasks", ["status"])
        op.create_index("ix_enrichment_tasks_priority", "enrichment_tasks", ["priority"])
        try:
            op.create_foreign_key(
                "fk_enrichment_tasks_icp",
                "enrichment_tasks",
                "icps",
                ["created_by_icp_id"],
                ["id"],
                ondelete="SET NULL",
            )
        except Exception:
            pass


def downgrade() -> None:
    op.drop_table("enrichment_tasks")
    for col in (
        "icp_score", "priority_tier", "lifecycle_stage", "revenue_band",
        "employee_count_band", "industry_standardized", "reason_summary",
        "last_scored_at", "scored_with_icp_id",
    ):
        try: op.drop_column("companies", col)
        except Exception: pass
