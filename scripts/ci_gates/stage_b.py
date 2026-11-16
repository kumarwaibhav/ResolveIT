"""Repeatable audit-only PostgreSQL16 migration and API integration gate.

Requires the task-owned, loopback-only resolveit-audit-pg container. Existing
databases are preserved except resolveit_test, intentionally reset by pytest's
fixture inside this dedicated audit cluster. Never point this gate at customers.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import asyncpg
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]
CONTAINER = "resolveit-audit-pg"


def run(args: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> bytes:
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, timeout=1800)
    if result.returncode:
        raise RuntimeError(f"Audit command failed with exit {result.returncode}; diagnostics withheld")
    return result.stdout


def verify_container() -> None:
    item = json.loads(run(["docker", "inspect", CONTAINER]))[0]
    if item["Config"].get("Labels", {}).get("resolveit.audit") != "true":
        raise RuntimeError("Refusing a container without the task-owned audit label")
    if not item["Config"]["Image"].startswith("postgres:16"):
        raise RuntimeError("Audit requires PostgreSQL16 image")
    bindings = item["HostConfig"]["PortBindings"].get("5432/tcp", [])
    if bindings != [{"HostIp": "127.0.0.1", "HostPort": "54329"}]:
        raise RuntimeError("Audit container must expose only loopback54329")
    if not item["State"]["Running"]:
        run(["docker", "start", CONTAINER])
    run(["docker", "update", "--memory", "384m", "--memory-swap", "512m", "--cpus", "1", CONTAINER])


async def create_database(database: str) -> None:
    conn = await asyncpg.connect("postgresql://postgres@127.0.0.1:54329/postgres")
    try:
        # Identifier is generated internally from UUID hexadecimal, never input.
        await conn.execute(f"CREATE DATABASE {database} OWNER resolveit_migrator")
    finally:
        await conn.close()


async def verify_revision(database: str, expected: list[str]) -> None:
    conn = await asyncpg.connect(f"postgresql://postgres@127.0.0.1:54329/{database}")
    try:
        actual = [row[0] for row in await conn.fetch("SELECT version_num FROM alembic_version")]
        if actual != expected:
            raise RuntimeError("Unexpected Alembic revision")
    finally:
        await conn.close()


async def catalog(database: str) -> dict[str, Any]:
    conn = await asyncpg.connect(f"postgresql://postgres@127.0.0.1:54329/{database}")
    try:
        tables = await conn.fetch(
            "SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,"
            "(SELECT count(*) FROM pg_policy p WHERE p.polrelid=c.oid) AS policies "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relkind='r' AND c.relname<>'alembic_version'"
        )
        if len(tables) != 20 or not all(
            row["relrowsecurity"] and row["relforcerowsecurity"] and row["policies"] == 1 for row in tables
        ):
            raise RuntimeError("Tenant table RLS/policy audit failed")
        foreign_keys = await conn.fetchval(
            "SELECT count(*) FROM pg_constraint WHERE contype='f' AND cardinality(conkey)=2"
        )
        if foreign_keys != 13:
            raise RuntimeError("Tenant-consistent foreign key audit failed")
        roles = await conn.fetch(
            "SELECT rolsuper,rolbypassrls FROM pg_roles "
            "WHERE rolname IN ('resolveit_app','resolveit_migrator')"
        )
        if len(roles) != 2 or any(row["rolsuper"] or row["rolbypassrls"] for row in roles):
            raise RuntimeError("Role privilege audit failed")
        for table, privileges in (
            ("billing_ledger", ("UPDATE", "DELETE")),
            ("api_keys", ("INSERT", "UPDATE", "DELETE")),
            ("connector_observation", ("INSERT", "UPDATE", "DELETE")),
            ("review_labels", ("UPDATE",)),
            ("review_exposures", ("UPDATE",)),
        ):
            for privilege in privileges:
                if await conn.fetchval("SELECT has_table_privilege('resolveit_app',$1,$2)", table, privilege):
                    raise RuntimeError("Protected table grant audit failed")
        for table, column, expected in (
            ("review_items", "split", False),
            ("review_items", "status", True),
            ("tenants", "timezone", True),
            ("tenants", "is_synthetic", False),
        ):
            actual = await conn.fetchval(
                "SELECT has_column_privilege('resolveit_app',$1,$2,'UPDATE')", table, column
            )
            if actual is not expected:
                raise RuntimeError("Protected column grant audit failed")
        if await conn.fetchval("SELECT has_schema_privilege('resolveit_app','public','CREATE')"):
            raise RuntimeError("App schema CREATE privilege forbidden")
        if await conn.fetchval("SELECT has_table_privilege('resolveit_app','alembic_version','SELECT')"):
            raise RuntimeError("App Alembic metadata access forbidden")
        functions = await conn.fetch(
            "SELECT p.prosecdef,p.proconfig,r.rolname FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_roles r ON r.oid=p.proowner "
            "WHERE n.nspname='public' AND p.proname IN "
            "('resolve_api_key','due_clarifications','due_outbox')"
        )
        if len(functions) != 3 or not all(
            row["prosecdef"]
            and row["rolname"] == "resolveit_auth"
            and row["proconfig"] == ["search_path=public, pg_temp"]
            for row in functions
        ):
            raise RuntimeError("Definer function audit failed")
        public = await conn.fetchval(
            "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a "
            "WHERE n.nspname='public' AND p.proname IN "
            "('resolve_api_key','due_clarifications','due_outbox') "
            "AND a.grantee=0 AND a.privilege_type='EXECUTE'"
        )
        if public:
            raise RuntimeError("PUBLIC definer execution forbidden")
        settings = {
            str(row["name"]): str(row["setting"])
            for row in await conn.fetch(
                "SELECT name,setting FROM pg_settings WHERE name IN ('shared_buffers','max_connections')"
            )
        }
        if settings != {"shared_buffers": "8192", "max_connections": "80"}:
            raise RuntimeError("Audit server resource configuration differs")
        return {
            "tenant_tables": 20,
            "composite_foreign_keys": 13,
            "definer_functions": 3,
            "restricted_grants": "verified",
        }
    finally:
        await conn.close()


def main() -> int:
    started = time.perf_counter()
    verify_container()
    database = f"resolveit_audit_{uuid4().hex}"
    asyncio.run(create_database(database))
    os.environ["RESOLVEIT_MIGRATOR_DATABASE_URL"] = (
        f"postgresql+asyncpg://resolveit_migrator:mig_dev_pw@127.0.0.1:54329/{database}"
    )
    cfg = Config(str(ROOT / "alembic.ini"))
    command.upgrade(cfg, "head")
    asyncio.run(verify_revision(database, ["0004"]))
    command.downgrade(cfg, "base")
    asyncio.run(verify_revision(database, []))
    command.upgrade(cfg, "head")
    asyncio.run(verify_revision(database, ["0004"]))
    receipt = asyncio.run(catalog(database))
    env = dict(os.environ, RESOLVEIT_TEST_SKIP_BOOTSTRAP="1", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2")
    run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT / "apps/api", env=env)
    run([sys.executable, "-m", "pytest", "-q", "tests/security"], env=env)
    receipt.update(
        {
            "passed": True,
            "database": database,
            "roundtrip": "0004 -> base -> 0004",
            "seconds": time.perf_counter() - started,
        }
    )
    print(json.dumps(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
