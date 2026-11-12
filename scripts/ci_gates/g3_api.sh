#!/usr/bin/env bash
# Gate G3 (partial): tenant isolation, intake, clarification, erasure, MCP 2026-07-28 flow,
# request-state tampering, worker timeouts and crash recovery, against a real Postgres 16.
# Not yet covered: webhook echo storm, outbox, log scan (they arrive with the Jira connector).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
bash "$ROOT/infra/dev/pg_local.sh" start
cd "$ROOT/apps/api"
ruff check . "$ROOT/enterprise" "$ROOT/apps/worker"
MYPYPATH="$ROOT/packages/resolveit-core:$ROOT/enterprise:$ROOT/apps/worker" \
  mypy resolveit_api "$ROOT/enterprise/resolveit_enterprise" "$ROOT/apps/worker/resolveit_worker"
python -m pytest -q
