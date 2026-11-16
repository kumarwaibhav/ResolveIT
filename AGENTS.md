# ResolveIT contributor contract

Read `docs/00_CODEX_AUDIT_AND_MASTER_PLAN.md`, then `docs/BUILD_STATE.md` when present. This is the canonical agent entrypoint. `CLAUDE.md` contains legacy guidance; resolve conflicts in favor of this file and the audited master plan.

## Sources and boundaries
- Pydantic v2 models in `packages/resolveit-core/resolveit_core/schemas/` own domain and API shapes. Generate OpenAPI and web types; do not hand-edit generated files.
- Core owns pure math/text processing; API owns persistence/auth; worker owns bounded background execution; web owns presentation; enterprise owns managed-key adapters.
- Preserve existing user edits. Assign non-overlapping files before concurrent writers. Isolated gatekeeper reviews and tests writers' artifacts.
- Every stage records commands, outcomes, limitations and next work in `docs/BUILD_STATE.md`. A scaffold, mock or unexecuted test is not a completed feature.

## Non-negotiable invariants
- Real tenants remain shadow/human-gated until shipped-model human audit data certifies their actual queue/action policy. Synthetic demonstrations cannot graduate real queues.
- Label provenance is explicit: `synthetic_seed`/legacy `synthetic`, `llm_silver`, and independent human annotations are distinct. Training corrections never silently enter calibration or frozen test splits.
- Fit temperature separately from conformal/risk certification. Calibrate exact shipped INT8 outputs; hash model, tokenizer, label maps, costs, thresholds, theta and policy together.
- Empty conformal set immediately DEFERs with `no_conforming_team`. `tau_hat=None` never ROUTEs. Missing/contradicted critical slots cannot bypass policy through exploration.
- Exploration asks at most one question, respects no-ask holdout, uses stable incident allocation, and records propensity. Beta(4,2) is an explicit configurable operational prior, not measured evidence.
- Raw rules precede normalization/masking. Evidence stays in raw Unicode code-point offsets; API converts to UTF-16 once. Preserve protected error codes and offset chains.
- Credentials determine tenant and role. Tenant SQL uses `tenant_tx`; every tenant table has ENABLE/FORCE RLS, tenant-consistent foreign keys and no app BYPASSRLS. Only narrowly scoped audited SECURITY DEFINER lookups cross tenants.
- Worker session advisory locks require direct Postgres; transaction-mode PgBouncer serves tenant transactions only.
- Ticket text, secrets and SQL bind values never enter logs/traces/metrics. Never print secret scan matches; report paths/counts only.
- AES-GCM key deletion in live DB does not erase backup copies. Production requires managed key lifecycle plus erasure tombstones replayed before restore exposure.
- Public web deployment requires authenticated sessions and per-principal tenant authorization. Shared demo server keys are loopback/synthetic-only.
- Standard MCP JSON-RPC lifecycle and tools are independent of opt-in ResolveIT enterprise MRTR extensions. Never invent protocol dates or claim SDK conformance without executed SDK tests.
- GPU/heavy CPU jobs use `scripts/gpu_guard.py` and exclusive `.runtime/heavy_job.lock`. Latest owner override (2026-11-16) removes arbitrary RAM/VRAM utilization ceilings: use physicalRAMavailable>=750MiB (pause below1024MiB, stop after3 consecutive low polls), freeVRAM>=512MiB, Windowscommit/swap<=88%, GPU pause>=75C for25s/hardstop>=78C. Training launch requires GPU<65C. These are emergency safety reserves, not a guarantee against OS/driver failure. Keep boundedCPU threads and only1-2 active agents; missing safety telemetry fails closed. Execute Phase2 stages sequentially; no overlapping heavy subsystems.
- Git commits use local configured author only; no AI co-author trailers. Never commit credentials, raw handoff transcript, model caches, generated secrets or customer text.

## Minimum validation
Run from repository root with environment installed:

```text
python -m ruff check packages/resolveit-core apps/api enterprise apps/worker scripts
python -m mypy --strict packages/resolveit-core/resolveit_core
python -m pytest packages/resolveit-core/tests
python -m pytest apps/api/tests
```

Run web `npx tsc --noEmit`, ESLint, Vitest, production build and Playwright/axe journeys from `apps/web`. Existing `scripts/ci_gates/g1_core.sh`, `g3_api.sh`, `g4_web.sh` document Linux gates; PostgreSQL/browser gates require live dependencies. Record blocked/not-run status accurately. Release additionally requires migrations up/down/up, real PostgreSQL RLS concurrency, webhook storms, exact-model bundle validation and runtime checks defined in master plan.
