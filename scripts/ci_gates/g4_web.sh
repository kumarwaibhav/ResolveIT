#!/usr/bin/env bash
# Gate G4 (partial): web app. Static checks always; browser journeys when the stack is up
# (start it with: bash scripts/dev_up.sh prod).
# Covered: generated contracts are current, types, lint, unit tests, colour contrast, build,
# route / ask-answer / ask-skip / agent hand-off journeys, highlight alignment, zero network
# calls while typing, axe WCAG 2.1 AA at 1280 px light and 320 px dark, no horizontal overflow.
# Not yet covered: review console, bounce analyzer, evaluation lab, settings (not built).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
python scripts/export_contracts.py
(cd apps/web && npm run -s gen:types >/dev/null)
git diff --exit-code -- apps/web/openapi.json apps/web/src/generated || { echo "generated contracts are stale"; exit 1; }
cd apps/web
npx tsc --noEmit
npx eslint .
npx vitest run
node scripts/check_contrast.mjs >/dev/null
npm run -s build >/dev/null
if curl -sf -m 3 http://127.0.0.1:3000/ >/dev/null && curl -sf -m 3 http://127.0.0.1:8000/healthz >/dev/null; then
  python e2e/journeys.py
else
  echo "stack not running: browser journeys NOT RUN"; exit 2
fi
