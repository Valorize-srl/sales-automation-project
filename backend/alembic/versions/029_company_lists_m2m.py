"""Add many-to-many company<->lead_list + colour/icon on lead_lists.

Revision ID: 029
"""
import sqlalchemy as sa
from alembic import op

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1. M2M table
    if "company_lead_list" not in inspector.get_table_names():
        op.create_table(
            "company_lead_list",
            sa.Column(
                "company_id", sa.Integer,
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "lead_list_id", sa.Integer,
                sa.ForeignKey("lead_lists.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_company_lead_list_list", "company_lead_list", ["lead_list_id"])

    # 2. Optional decoration columns on lead_lists
    if "lead_lists" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("lead_lists")}
        if "color" not in existing_cols:
            op.add_column("lead_lists", sa.Column("color", sa.String(20), nullable=True))
        if "icon" not in existing_cols:
            op.add_column("lead_lists", sa.Column("icon", sa.String(40), nullable=True))


def downgrade() -> None:
    op.drop_index("ix_company_lead_list_list", table_name="company_lead_list")
    op.drop_table("company_lead_list")
    for c in ("color", "icon"):
        try: op.drop_column("lead_lists", c)
        except Exception: pass
