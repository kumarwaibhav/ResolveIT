"""Initial forced-RLS schema; preserves the audited original SQL."""

from pathlib import Path

import sqlparse
from alembic import op

revision = "0001"
down_revision = None


def upgrade() -> None:
    source = Path(__file__).resolve().parents[2] / "0001_init.sql"
    for statement in sqlparse.split(source.read_text(encoding="utf-8")):
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP FUNCTION resolve_api_key(text)")
    for table in (
        "erasure_requests",
        "channel_stats",
        "questions",
        "decisions",
        "frames",
        "subject_index",
        "incident_text",
        "incident_keys",
        "incidents",
        "api_keys",
        "tenants",
    ):
        op.execute(f"DROP TABLE {table}")
