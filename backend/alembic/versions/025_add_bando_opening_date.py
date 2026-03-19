"""Add opening_date column to bandi table.

Revision ID: 025
"""
import sqlalchemy as sa
from alembic import op

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if column already exists (idempotent)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "bandi" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("bandi")]
        if "opening_date" not in columns:
            op.add_column(
                "bandi",
                sa.Column("opening_date", sa.DateTime(timezone=True), nullable=True),
            )
            op.create_index("ix_bandi_opening_date", "bandi", ["opening_date"])


def downgrade() -> None:
    op.drop_index("ix_bandi_opening_date", table_name="bandi")
    op.drop_column("bandi", "opening_date")
