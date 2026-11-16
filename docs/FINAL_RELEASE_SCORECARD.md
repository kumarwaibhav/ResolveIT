# ResolveIT release scorecard — provisional

Updated 2026-11-17, Asia/Calcutta. External production authorization: **false**.
This scorecard records the fresh G0–G6 run below and earlier phase receipts.
It is not a production-readiness certificate.

## Fresh gate run, 2026-11-17 (commits 75648b1 / f2612d7, bundle 968fd32c...)

Runner: `scripts/ci_gates/run_all_gates.py --expected-id 968fd32c1e2b50b9dd7a5cd99ed458923137f4680454cd32c6fc5922adf5d238`
(G3-G6 rerun with `--keep-engine` after Docker Desktop stale-socket start failures).

| Gate | Result | Evidence |
| --- | --- | --- |
| G0 | PASSED | repo hygiene (Protocol members no longer flagged as stubs), history + staged secret scan 0 findings |
| G1 | PASSED | ruff, strict mypy core + API/enterprise/worker, pytest core/scripts/release/training |
| G2 | **FAILED (by design, honest)** | bundle verifies against pinned id; 128-token encoder p95 197 ms vs 50 ms target. Typical ticket full pipeline p50 40 / p95 45 ms. Needs distilled student (training v2) |
| G3 | PASSED | migrations 0004 -> base -> 0004 round trip, API integration suite, security suite on PostgreSQL 16 |
| G4 | PASSED | typecheck, lint, vitest, production build, live native runtime: official MCP SDK, MRTR, 12 axe scans 0 violations |
| G5 | PASSED | API/web/PgBouncer Linux images built; live Compose stack drill |
| G6 | PASSED (scoped) | same-run Stage D: same-code configuration rollback, restore/erasure tombstone replay; cross-version schema rollback NOT verified |

Overall: **not production-authorized** (G2 latency target, synthetic provenance, no human gold).
Live showcase smoke (`scripts/showcase_smoke.py`) passed: clear route, one-question route, compound ask,
security escalation.

## Measured phase receipts

- PhaseB full integration:53 passed in36.19s; migration rehearsal3.703s. All20
  tenant tables had ENABLE/FORCE RLS;13 composite foreign keys; three restricted
  definer functions; application/migrator roles NOSUPERUSER/NOBYPASSRLS.
- PhaseC incident POST first239.978ms; warm30 requests p50/p95
  203.043/255.621ms. ONNX toy fixture load+first10.324ms and warm200 after200
  warmups p50/p95 0.03045/0.046305ms. These ONNX numbers are **not** mDeBERTa latency.
- PhaseD live stack drill53.4323s; five steady memory caps total1344MiB;
  100 pooled transactions, maximum prepared-statement count1; direct worker
  advisory-lock exclusion/release passed. No OOM kills observed.
- PhaseD endpoint samples: RAM76.8→77.5%, available3758→3648MiB,
  Windows commit51.33→51.49%, GPU53°C. These samples are not measured peaks.

Receipts: `docs/audits/stage_b.md`, `stage_c.md`, `stage_d.md` and private ignored
`artifacts/stage-c/receipt.json`, `artifacts/stage-d/receipt.json`.

## Honest prerequisites before external production traffic

- Actual pretrained training/export/calibration, integrity and latency gates must
  finish. A release-candidate artifact is distinct from API serving integration;
  existing tested API bundles remain rule-based demonstrations/shadow bundles.
- Real tenants remain shadow/human-gated. Synthetic or silver certification never
  authorizes real routing. No independent human-gold frozen-test result exists.
- Automated synthetic review identities/test annotations do not constitute verified
  human annotation. API provenance `human_on_synthetic` on the test tenant must not
  be described as a real human-gold dataset.
- Jira echo tests are inbox/guard simulations, not a configured external Jira
  connector. A2A interoperability and customer integrations remain independent gates.
- Live wrapped-key deletion alone does not erase backups. Managed KMS revocation,
  restore tombstone replay enforcement, backup retention and derived-copy policies
  require operational ownership and independent verification.
- Current rollback receipt covers the same immutable code image with a deliberately
  broken configuration. Cross-version schema compatibility/rollback remains untested.
- Distributed gateway quotas, production credential/identity lifecycle, managed-key
  credentials, monitoring and deployment-specific operating procedures remain required.
- A missing external zero-shot baseline must remain unavailable; synthetic/silver
  family bias and template overlap must remain explicit in benchmark reports.

## Rerun commands

Inspect without acquiring a heavy-job slot:

```powershell
.venv/Scripts/python.exe scripts/ci_gates/run_all_gates.py --plan
```

After ML releases the exclusive mutex and source freezes:

```powershell
.venv/Scripts/python.exe scripts/ci_gates/run_all_gates.py --expected-id <trusted-bundle-id>
```

The runner writes per-command exit codes, durations and output hashes to ignored
`artifacts/release-gates/receipt.json`; arbitrary raw diagnostics are not persisted.
Missing prerequisites, unexecuted commands and dirty-tree failures never count as
passed. G6 can consume only the fresh StageD result from the same invocation.
