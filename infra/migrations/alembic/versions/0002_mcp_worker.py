"""MCP deduplication and bounded cross-tenant deadline discovery."""

from pathlib import Path

import sqlparse
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    source = Path(__file__).resolve().parents[2] / "0002_mcp_and_worker.sql"
    for statement in sqlparse.split(source.read_text(encoding="utf-8")):
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP FUNCTION due_clarifications(integer)")
    op.execute("DROP TABLE mcp_calls")
    op.execute(
        "REVOKE SELECT (id, tenant_id, state, clarify_deadline) ON incidents FROM resolveit_auth"
    )
