"""Add raw revenue, employee_count, and custom_fields JSONB to companies.

Revision ID: 028
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "companies" not in inspector.get_table_names():
        return

    existing = {c["name"] for c in inspector.get_columns("companies")}
    if "revenue" not in existing:
        op.add_column("companies", sa.Column("revenue", sa.BigInteger(), nullable=True))
    if "employee_count" not in existing:
        op.add_column("companies", sa.Column("employee_count", sa.Integer(), nullable=True))
    if "custom_fields" not in existing:
        op.add_column(
            "companies",
            sa.Column("custom_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
    if "province" not in existing:
        op.add_column("companies", sa.Column("province", sa.String(10), nullable=True))


def downgrade() -> None:
    for c in ("revenue", "employee_count", "custom_fields", "province"):
        try:
            op.drop_column("companies", c)
        except Exception:
            pass
