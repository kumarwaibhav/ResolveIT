"""Guarded local Compose, restore/tombstone and configuration rollback rehearsal.

Requires already-built stage-d images. Never deletes volumes or existing databases.
Only synthetic local records are written. Backups contain local secrets: ignored
artifacts are private and must not be published.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from uuid import uuid4

from gpu_guard import ResourceGuard

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/stage-d"
DEMO = "00000000-0000-4000-8000-000000000001"


def command(*args: str, data: bytes | None = None, timeout: int = 180) -> bytes:
    result = subprocess.run(args, cwd=ROOT, input=data, capture_output=True, timeout=timeout)
    if result.returncode:
        # Diagnostics may contain credentials/SQL parameters; never print them.
        raise RuntimeError(f"Command {args[0]} {args[1]} failed with exit {result.returncode}")
    return result.stdout


def compose(*args: str, data: bytes | None = None, timeout: int = 180) -> bytes:
    return command("docker", "compose", *args, data=data, timeout=timeout)


def sql(query: str, database: str = "resolveit") -> str:
    return (
        compose(
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "postgres",
            "-d",
            database,
            "-v",
            "ON_ERROR_STOP=1",
            "-Atc",
            query,
        )
        .decode()
        .strip()
    )


def request(url: str, key: str | None = None, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    headers = {"content-type": "application/json"}
    if key:
        headers["authorization"] = f"Bearer {key}"
    req = urllib.request.Request(
        url, headers=headers, data=None if body is None else json.dumps(body).encode()
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = response.read()
            return response.status, json.loads(data) if "application/json" in response.headers.get(
                "content-type", ""
            ) else None
    except urllib.error.HTTPError as exc:
        return exc.code, None


def wait(url: str, *, key: str | None = None, attempts: int = 90) -> None:
    for _ in range(attempts):
        with contextlib.suppress(OSError, ValueError):
            if request(url, key)[0] == 200:
                return
        time.sleep(2)
    raise RuntimeError("Readiness deadline exceeded")


def pool_and_lock() -> dict[str, Any]:
    pool = compose(
        "exec",
        "-T",
        "api",
        "python",
        "-c",
        """
import asyncio,json,os
from uuid import UUID
from sqlalchemy import text
from resolveit_api.db.session import Database
async def main():
 d=Database(os.environ['RESOLVEIT_APP_DATABASE_URL'])
 assert '@pgbouncer:' in os.environ['RESOLVEIT_APP_DATABASE_URL']
 async with d.tenant_tx(UUID('00000000-0000-4000-8000-000000000001')) as s:
  assert (await s.execute(text('SELECT count(*) FROM tenants'))).scalar()==1
  role=text('SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user')
  assert (await s.execute(role)).scalar() is False
 async with d._engine.connect() as c:
  setting=text("SELECT NULLIF(current_setting('app.current_tenant_id',true),'')")
  assert (await c.execute(setting)).scalar() is None
 counts=[]
 for _ in range(100):
  async with d.tenant_tx(UUID('00000000-0000-4000-8000-000000000001')) as s:
   counts.append((await s.execute(text('SELECT count(*) FROM pg_prepared_statements'))).scalar())
 assert max(counts)<=10, 'Prepared statements accumulated across pooled transactions'
 await d.dispose()
 print(json.dumps({'pool_host_verified':True,'tenant_transaction':True,'setting_reset':True,
  'no_bypass':True,'repeated_transactions':100,'max_prepared_statement_count':max(counts)}))
asyncio.run(main())
""",
    )
    lock = compose(
        "exec",
        "-T",
        "worker",
        "python",
        "-c",
        """
import asyncio,json,os
from resolveit_api.db.session import Database
async def main():
 assert '@postgres:' in os.environ['RESOLVEIT_APP_DATABASE_URL']
 d=Database(os.environ['RESOLVEIT_APP_DATABASE_URL'])
 async with d.leader_lock(73999001) as first:
  async with d.leader_lock(73999001) as second:
   assert first and not second
 async with d.leader_lock(73999001) as released:
  assert released
 await d.dispose()
 print(json.dumps({'direct_worker_host_verified':True,'session_lock_exclusion_and_release':True}))
asyncio.run(main())
""",
    )
    config = compose("exec", "-T", "pgbouncer", "cat", "/etc/resolveit/pgbouncer.ini").decode()
    assert "pool_mode = transaction" in config
    return {**json.loads(pool), **json.loads(lock), "running_pool_configuration": "transaction"}


def erasure_drill(key: str) -> dict[str, Any]:
    identifier = f"stage-d-{uuid4().hex}@example.invalid"
    status, incident = request(
        "http://127.0.0.1:8000/v1/incidents",
        key,
        {"text": f"Database unavailable for {identifier}", "locale": "en"},
    )
    assert status == 200 or status == 201
    incident_id = str(incident["id"])
    assert sql(f"SELECT count(*) FROM incident_keys WHERE incident_id='{incident_id}'") == "1"
    backup = compose("exec", "-T", "postgres", "pg_dump", "-U", "postgres", "-d", "resolveit", "-Fc")
    backup_file = ART / "synthetic-before-erasure.dump"
    backup_file.write_bytes(backup)
    if os.name != "nt":
        backup_file.chmod(0o600)
    status, erased = request(
        "http://127.0.0.1:8000/v1/privacy/erasure", key, {"kind": "EMAIL", "identifier": identifier}
    )
    assert status == 200 and erased["incidents_erased"] == 1
    tombstone = {"tenant_id": DEMO, "incident_id": incident_id, "state": "ERASED"}
    (ART / "erasure-tombstone.json").write_text(json.dumps(tombstone), encoding="utf-8")
    database = "resolveit_restore_" + uuid4().hex[:12]
    sql(f"CREATE DATABASE {database} OWNER resolveit_migrator")
    compose(
        "exec",
        "-T",
        "postgres",
        "pg_restore",
        "-U",
        "postgres",
        "-d",
        database,
        "--exit-on-error",
            "--clean",
            "--if-exists",
        data=backup,
    )
    # Negative control: restoring a pre-erasure backup resurrects the wrapped key.
    assert sql(f"SELECT count(*) FROM incident_keys WHERE incident_id='{incident_id}'", database) == "1"
    replay = f"""
BEGIN;
SELECT set_config('app.current_tenant_id','{DEMO}',true);
SELECT id FROM incidents WHERE id='{incident_id}' FOR UPDATE;
DELETE FROM incident_keys WHERE incident_id='{incident_id}';
UPDATE incident_text SET masked_text=NULL,raw_ciphertext=NULL,raw_nonce=NULL,tombstoned_at=now()
 WHERE incident_id='{incident_id}';
DELETE FROM subject_index WHERE incident_id='{incident_id}';
DELETE FROM frames WHERE incident_id='{incident_id}';
DELETE FROM questions WHERE incident_id='{incident_id}';
DELETE FROM review_labels WHERE incident_id='{incident_id}';
DELETE FROM review_items WHERE incident_id='{incident_id}';
UPDATE decisions SET payload='{{}}'::jsonb WHERE incident_id='{incident_id}';
UPDATE incidents SET state='ERASED',clarify_deadline=NULL,version=version+1 WHERE id='{incident_id}';
COMMIT;
"""
    sql(replay, database)
    assert sql(f"SELECT state FROM incidents WHERE id='{incident_id}'", database) == "ERASED"
    for table in ("incident_keys", "frames", "questions", "review_labels", "review_items", "subject_index"):
        assert sql(f"SELECT count(*) FROM {table} WHERE incident_id='{incident_id}'", database) == "0"
    assert (
        sql(
            "SELECT raw_ciphertext IS NULL AND raw_nonce IS NULL AND masked_text IS NULL "
            f"FROM incident_text WHERE incident_id='{incident_id}'",
            database,
        )
        == "t"
    )
    assert (
        sql(
            "SELECT count(*) FROM pg_class WHERE relkind='r' AND relrowsecurity AND relforcerowsecurity",
            database,
        )
        == "20"
    )
    return {
        "backup_sha256": hashlib.sha256(backup).hexdigest(),
        "restore_database": database,
        "negative_control_key_restored": True,
        "external_tombstone_replay_passed": True,
        "backup_wide_cryptoshredding_without_replay": False,
    }


def rollback() -> dict[str, Any]:
    # Same immutable code image, different deployment configuration. This exercises
    # actual local traffic cutover/rollback, not compatibility with an older schema.
    image = (
        command("docker", "image", "inspect", "resolveit-web:stage-d", "--format", "{{.Id}}").decode().strip()
    )
    compose(
        "run",
        "-d",
        "--no-deps",
        "--name",
        "resolveit-stage-d-green",
        "-p",
        "127.0.0.1:3001:3000",
        "-e",
        "RESOLVEIT_API_URL=http://127.0.0.1:9",
        "web",
    )
    selected = [3000]

    class Proxy(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            try:
                status, _ = request(f"http://127.0.0.1:{selected[0]}{self.path}")
            except OSError:
                status = 502
            self.send_response(status)
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 3002), Proxy)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        wait("http://127.0.0.1:3001")
        assert request("http://127.0.0.1:3002/api/workspaces/evaluation")[0] == 200
        selected[0] = 3001
        assert request("http://127.0.0.1:3002/api/workspaces/evaluation")[0] >= 500
        selected[0] = 3000
        assert request("http://127.0.0.1:3002/api/workspaces/evaluation")[0] == 200
        return {
            "blue_image_id": image,
            "green_image_id": image,
            "cutover_smoke_failure": True,
            "rollback_recovered": True,
            "scope": "same-code pinned-image configuration regression",
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        command("docker", "stop", "resolveit-stage-d-green")
        command("docker", "rm", "resolveit-stage-d-green")


def main() -> int:
    ART.mkdir(parents=True, exist_ok=True)
    guard = ResourceGuard()
    start = time.perf_counter()
    receipt: dict[str, Any] = {"provenance": "synthetic_seed", "production_authorized": False}
    values = dict(
        line.split("=", 1)
        for line in (ROOT / ".env").read_text().splitlines()
        if line and not line.startswith("#") and "=" in line
    )
    key = values["RESOLVEIT_API_KEY"]
    try:
        receipt["before"] = vars(guard.checkpoint())
        compose("up", "-d", "--no-build", timeout=240)
        wait("http://127.0.0.1:8000/healthz")
        wait("http://127.0.0.1:8000/v1/me", key=key)
        status, identity = request("http://127.0.0.1:8000/v1/me", key)
        assert status == 200 and identity["is_synthetic"] is True and identity["tenant_id"] == DEMO
        wait("http://127.0.0.1:3000")
        receipt["pool_and_worker"] = pool_and_lock()
        receipt["backup_restore_erasure"] = erasure_drill(key)
        receipt["blue_green"] = rollback()
        receipt["containers"] = [json.loads(line) for line in compose("ps", "--format", "json").splitlines()]
        receipt["after"] = vars(guard.sample())
        receipt["elapsed_seconds"] = time.perf_counter() - start
        receipt["passed"] = True
        print(
            "Compose readiness, tenant transaction, direct worker lock, restore replay and rollback passed."
        )
        return 0
    finally:
        compose("stop", timeout=120)
        guard.close()
        (ART / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
