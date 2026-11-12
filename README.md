# ResolveIT

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
