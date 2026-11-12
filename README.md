# ResolveIT

Calibrated IT incident framing and routing. Built so far:

| Part | Path | State |
| --- | --- | --- |
| Core: contracts, OffsetMap, rules, PII masker, calibration, gate, evidence | `packages/resolveit-core` | Tested (gate G1) |
| Question templates, 11 authored seeds | `packages/resolveit-frames` | hi / hinglish unreviewed |
| Schema with forced row-level security | `infra/migrations` | Tested |
| API: persist-first intake, one optional question, erasure | `apps/api` | Tested (gate G3, partial) |
| Encryption, blind index, crypto-shredding | `enterprise/resolveit_enterprise/privacy` | Tested; local key wrapper is dev-only |

Not built yet: trained model and ONNX bundle, worker (timeouts, outbox), Jira connector,
MCP endpoint, web app, deployment.

## Run the gates

    pip install -e "packages/resolveit-core[dev]" -e "apps/api[dev]"
    bash scripts/ci_gates/g1_core.sh
    bash scripts/ci_gates/g3_api.sh     # needs Postgres 16 binaries; starts a throwaway cluster

## What the API does today, honestly

- No trained model exists. Team probabilities come from hand-set rule weights.
- Real tenants get the **shadow bundle**: uncalibrated, `tau_hat = None`, never auto-routes.
  It returns a frame, evidence and a recommended team for a human.
- Tenants flagged `is_synthetic` get a bundle calibrated on generated tickets so the full
  ROUTE / ASK / DEFER flow can be shown. Its numbers describe the generator, nothing else.

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
