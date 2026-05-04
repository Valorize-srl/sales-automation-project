"""Strong dedup (unique-by-lower indexes), verification cache, and activity_log.

Revision ID: 030
"""
import sqlalchemy as sa
from alembic import op

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # ---- 1. Verification cache columns on people ----
    if "people" in inspector.get_table_names():
        existing = {c["name"] for c in inspector.get_columns("people")}
        for col, ctype in [
            ("last_email_verified_at", sa.DateTime(timezone=True)),
            ("email_verification_source", sa.String(50)),
            ("last_phone_verified_at", sa.DateTime(timezone=True)),
            ("phone_verification_source", sa.String(50)),
        ]:
            if col not in existing:
                op.add_column("people", sa.Column(col, ctype, nullable=True))

    # ---- 2. Functional unique indexes (case-insensitive) ----
    # Wrap in try/except so a re-run on data with later duplicates doesn't break boot.
    if "companies" in inspector.get_table_names():
        existing_idx = {i["name"] for i in inspector.get_indexes("companies")}
        if "uq_companies_name_lower" not in existing_idx:
            try:
                op.execute("CREATE UNIQUE INDEX uq_companies_name_lower ON companies (LOWER(name))")
            except Exception:
                pass

    if "people" in inspector.get_table_names():
        existing_idx = {i["name"] for i in inspector.get_indexes("people")}
        if "uq_people_email_lower" not in existing_idx:
            try:
                op.execute("CREATE UNIQUE INDEX uq_people_email_lower ON people (LOWER(email)) WHERE email IS NOT NULL")
            except Exception:
                pass

    # ---- 3. activity_log table ----
    if "activity_log" not in inspector.get_table_names():
        op.create_table(
            "activity_log",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("target_type", sa.String(20), nullable=False),  # 'account' | 'contact'
            sa.Column("target_id", sa.Integer, nullable=False),
            sa.Column("action", sa.String(80), nullable=False),
            sa.Column("payload", sa.JSON, nullable=True),
            sa.Column("actor", sa.String(40), nullable=True),  # 'user' | 'system' | 'mcp' | api_key id, etc.
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_activity_log_target", "activity_log", ["target_type", "target_id"])
        op.create_index("ix_activity_log_created", "activity_log", ["created_at"])
        op.create_index("ix_activity_log_action", "activity_log", ["action"])


def downgrade() -> None:
    op.drop_index("ix_activity_log_action", table_name="activity_log")
    op.drop_index("ix_activity_log_created", table_name="activity_log")
    op.drop_index("ix_activity_log_target", table_name="activity_log")
    op.drop_table("activity_log")
    op.execute("DROP INDEX IF EXISTS uq_people_email_lower")
    op.execute("DROP INDEX IF EXISTS uq_companies_name_lower")
    for col in ("last_email_verified_at", "email_verification_source",
                "last_phone_verified_at", "phone_verification_source"):
        try: op.drop_column("people", col)
        except Exception: pass
