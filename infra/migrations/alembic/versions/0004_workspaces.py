"""Persistent review, trusted annotator identities, settings and immutable dataset splits."""

from pathlib import Path

import sqlparse
from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade() -> None:
    source = Path(__file__).resolve().parents[2] / "0004_workspaces.sql"
    for statement in sqlparse.split(source.read_text(encoding="utf-8")):
        op.execute(statement)


def downgrade() -> None:
    op.execute("GRANT INSERT,UPDATE,DELETE ON api_keys TO resolveit_app")
    op.execute("GRANT UPDATE ON tenants TO resolveit_app")
    for table in ("review_exposures", "review_labels", "review_items", "tenant_settings", "connector_observation"):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION resolve_api_key(text)")
    op.execute("ALTER TABLE api_keys DROP COLUMN human_subject_id")
    op.execute("CREATE FUNCTION resolve_api_key(p_hash text) RETURNS TABLE (tenant_id uuid, role text) LANGUAGE sql STABLE SECURITY DEFINER SET search_path=public,pg_temp AS $$ SELECT k.tenant_id,k.role FROM api_keys k WHERE k.key_hash=p_hash AND k.revoked_at IS NULL $$")
    op.execute("GRANT CREATE ON SCHEMA public TO resolveit_auth")
    op.execute("ALTER FUNCTION resolve_api_key(text) OWNER TO resolveit_auth")
    op.execute("REVOKE CREATE ON SCHEMA public FROM resolveit_auth")
    op.execute("REVOKE ALL ON FUNCTION resolve_api_key(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION resolve_api_key(text) TO resolveit_app")
