"""Tenant-consistent foreign keys, durable delivery and append-only billing chain."""

from pathlib import Path

import sqlparse
from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade() -> None:
    source = Path(__file__).resolve().parents[2] / "0003_delivery_ledger.sql"
    for statement in sqlparse.split(source.read_text(encoding="utf-8")):
        op.execute(statement)


def downgrade() -> None:
    op.execute("ALTER TABLE mcp_calls DROP COLUMN request_digest")
    op.execute("GRANT DELETE ON tenants, incidents TO resolveit_app")
    op.execute("DROP FUNCTION due_outbox(integer)")
    for table in ("billing_ledger", "outbox", "inbox"):
        op.execute(f"DROP TABLE {table}")
    for table in (
        "incident_keys",
        "incident_text",
        "subject_index",
        "frames",
        "decisions",
        "questions",
        "mcp_calls",
    ):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_tenant_incident_fk")
    op.execute("ALTER TABLE incidents DROP CONSTRAINT incidents_tenant_parent_fk")
    op.execute("ALTER TABLE incidents DROP CONSTRAINT incidents_tenant_identity")
