#!/usr/bin/env bash
# Gate G3 (partial): tenant isolation, intake, clarification, erasure, against a real Postgres 16.
# Not yet covered: webhook echo storm, MCP conformance, outbox crash recovery, log scan.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
bash "$ROOT/infra/dev/pg_local.sh" start
cd "$ROOT/apps/api"
ruff check . "$ROOT/enterprise"
MYPYPATH="$ROOT/packages/resolveit-core:$ROOT/enterprise" mypy resolveit_api "$ROOT/enterprise/resolveit_enterprise"
python -m pytest -q
