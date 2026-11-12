#!/usr/bin/env bash
# Local demo: Postgres, migrations, synthetic tenant, API on :8000, web on :3000.
# Writes apps/web/.env.local (git-ignored). Stop with: kill $(cat /tmp/resolveit-*.pid)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PGBIN="${PGBIN:-/usr/lib/postgresql/16/bin}"; PORT="${PGPORT:-54329}"
bash "$ROOT/infra/dev/pg_local.sh" start
psql() { "$PGBIN/psql" -h 127.0.0.1 -p "$PORT" -v ON_ERROR_STOP=1 -q "$@"; }
psql -U postgres -c "DROP DATABASE IF EXISTS resolveit_dev WITH (FORCE)" -c "CREATE DATABASE resolveit_dev OWNER resolveit_migrator"
for f in "$ROOT"/infra/migrations/*.sql; do PGPASSWORD=mig_dev_pw psql -U resolveit_migrator -d resolveit_dev -f "$f"; done
export PYTHONPATH="$ROOT/apps/api:$ROOT/packages/resolveit-core:$ROOT/enterprise:$ROOT/apps/worker"
{ echo "RESOLVEIT_API_URL=http://127.0.0.1:8000"; python "$ROOT/scripts/seed_demo.py"; } > "$ROOT/apps/web/.env.local"
export RESOLVEIT_APP_DATABASE_URL="postgresql+asyncpg://resolveit_app:app_dev_pw@127.0.0.1:$PORT/resolveit_dev"
export RESOLVEIT_MASTER_KEY_B64="${RESOLVEIT_MASTER_KEY_B64:-$(python -c 'import base64,os;print(base64.b64encode(os.urandom(32)).decode())')}"
setsid nohup python -m uvicorn --factory resolveit_api.main:create_app --host 127.0.0.1 --port 8000 \
  >/tmp/resolveit-api.log 2>&1 </dev/null & echo $! >/tmp/resolveit-api.pid
cd "$ROOT/apps/web"
MODE=dev; if [ "${1:-dev}" = "prod" ]; then npm run -s build; MODE=start; fi
setsid nohup node node_modules/next/dist/bin/next "$MODE" -p 3000 >/tmp/resolveit-web.log 2>&1 </dev/null &
echo $! >/tmp/resolveit-web.pid
echo "API http://127.0.0.1:8000  ·  Web http://127.0.0.1:3000"
