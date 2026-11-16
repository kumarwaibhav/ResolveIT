#!/bin/sh
# Migrate (idempotent), run the worker beside the API, and stop the container if either exits.
set -eu
python scripts/bootstrap_db.py
python -m resolveit_worker.runner &
WORKER=$!
python -m uvicorn resolveit_api.main:create_app --factory --host 0.0.0.0 --port "${PORT:-7860}" \
  --no-access-log --proxy-headers --forwarded-allow-ips='*' &
API=$!
trap 'kill $WORKER $API 2>/dev/null' TERM INT
while kill -0 $WORKER 2>/dev/null && kill -0 $API 2>/dev/null; do sleep 5; done
kill $WORKER $API 2>/dev/null || true
exit 1
