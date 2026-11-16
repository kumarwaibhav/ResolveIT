# ResolveIT AI

Multilingual incident framing, conservative routing and human review. Active
enterprise build: audited source and local synthetic execution; production release
is gated on the evidence below. Never interpret synthetic scores as human accuracy.

Current implementation includes forced-RLS PostgreSQL tenant transactions,
reversible Alembic migrations, defensive dual-profile MCP, transactional delivery
and billing primitives, persistent blind human review, tenant settings, CSV bounce
analysis and six responsive enterprise workspaces. Browser credential sessions are
encrypted, expire after one hour and revalidate API credentials upstream. Real
tenants remain human-gated until supported shipped-model calibration exists.

Start with [local runtime instructions](docs/LOCAL_RUNTIME.md). For resumable work,
read [build checkpoint](docs/BUILD_STATE.md), [audited master plan](docs/00_CODEX_AUDIT_AND_MASTER_PLAN.md)
and [contributor contract](AGENTS.md). Specialist reports live in `docs/audits/`.

```powershell
python scripts/local_env.py
python scripts/gpu_guard.py -- docker compose build
docker compose up -d
```

Ports publish to loopback only. Generated secrets remain in ignored `.env`.
Compose syntax validation is separate from a successful fresh image build/boot;
consult the checkpoint for actual execution status.

Verified synthetic INT8 fixture demonstrates three-head training/export,
opset17 quantization, parity checks and disjoint calibration splits. Full
mDeBERTa LoRA entrypoint exists but pretrained training remains unverified.
Human gold, independent frozen-test results, external Jira/A2A interoperability,
managed backup erasure and production operational drills remain release gates.
The Jira guards and observation-gated72h ledger are infrastructure primitives;
they do not establish a configured external connector or completed billing service.

Latest safety profile uses available memory rather than RAM/VRAM utilization caps:
750MiB physical RAM emergency floor,512MiB free VRAM reserve, Windows commit/swap
safety checks, GPU pause>=75C/stop>=78C. Exclusive heavy-job mutex enforced.
Heavy jobs must use `scripts/gpu_guard.py`.

## Historical baseline at b5b8612

The original handoff inventory follows for provenance. Its feature and test statuses
describe the baseline; current state and executed evidence are in `docs/BUILD_STATE.md`.

Calibrated IT incident framing and routing. Built so far:

| Part | Path | State |
| --- | --- | --- |
| Core: contracts, OffsetMap, rules, PII masker, calibration, gate, evidence | `packages/resolveit-core` | Tested (gate G1) |
| Question templates, 11 authored seeds | `packages/resolveit-frames` | hi / hinglish unreviewed |
| Schema with forced row-level security | `infra/migrations` | Tested |
| API: persist-first intake, one optional question, erasure | `apps/api` | Tested (gate G3, partial) |
| MCP endpoint, protocol 2026-07-28, signed request state | `apps/api/resolveit_api/routes/mcp.py` | Tested; see note below |
| Worker: clarification timeouts, crash recovery, leader lock | `apps/worker` | Tested |
| Web app: intake with on-device detail meter, evidence view, agent hand-off simulator | `apps/web` | Tested (gate G4, partial) |
| Encryption, blind index, crypto-shredding | `enterprise/resolveit_enterprise/privacy` | Tested; local key wrapper is dev-only |

Not built yet: trained model and ONNX bundle, outbox, Jira connector, review console, bounce
analyzer, evaluation lab, settings, deployment.

## Run the gates

    pip install -e "packages/resolveit-core[dev]" -e "apps/api[dev]"
    bash scripts/ci_gates/g1_core.sh
    bash scripts/ci_gates/g3_api.sh     # needs Postgres 16 binaries; starts a throwaway cluster

## Run the demo locally

    (cd apps/web && npm ci)
    bash scripts/dev_up.sh prod         # Postgres, migrations, synthetic tenant, API :8000, web :3000
    bash scripts/ci_gates/g4_web.sh     # static checks plus browser journeys against the running stack

The web app is Next.js 15 (App Router), TypeScript, Tailwind 4 and shadcn/ui. Its API types and
the on-device rule patterns are generated from the Python source by `scripts/export_contracts.py`;
the gate fails if they are stale. API keys stay on the Next.js server.

## What the API does today, honestly

- No trained model exists. Team probabilities come from hand-set rule weights.
- Real tenants get the **shadow bundle**: uncalibrated, `tau_hat = None`, never auto-routes.
  It returns a frame, evidence and a recommended team for a human.
- Tenants flagged `is_synthetic` get a bundle calibrated on generated tickets so the full
  ROUTE / ASK / DEFER flow can be shown. Its numbers describe the generator, nothing else.

## MCP conformance note

Built from the published 2026-07-28 changelog and the multi round-trip requests page: required
headers, `resultType`, `input_required` with `inputRequests` and `requestState`, error codes
-32020 and -32022, `traceparent` in `_meta`. Two details were not confirmed against the schema
file and may need a small change: that `inputResponses` and `requestState` sit directly under
`params` on the retry, and the exact field names of the `server/discover` result. It has not
been run against an official SDK client.

## Open design items found while building

1. **Ask cold start.** With no response history the Beta(1, 1) prior gives rho = 0.5 and, at
   default costs, asking never pays, so no history is ever collected. Needs a measured prior
   from the Step 0 response study or a small forced-exploration rate.
2. **Selective-risk power.** The top-down tau walk stops at the first failing step. A noisy
   high-confidence bin, or about 1,800 calibration points, often certifies nothing.
3. **Empty conformal set.** The gate forbids ROUTE on an empty set but still considers one
   question; it defers with `no_conforming_team` only if no question is worth asking.
4. **Default costs** (240 min misroute, 45 min triage, per-channel ask costs) are placeholders
   until real bounce data exists.
5. **Migrations** are plain numbered SQL, not Alembic yet.
