# ResolveIT release scorecard — provisional

Updated 2026-11-15, Asia/Calcutta. External production authorization: **false**.
This scorecard separates executed phase receipts from the final G0–G6 rerun.
It is not a production-readiness certificate. Final gates have not been executed
by the isolated release gatekeeper while the single heavy-job slot belongs to ML.

| Gate | Earlier executed evidence | Fresh final gate status |
| --- | --- | --- |
| G0 | 122 reachable historical blobs and local Git configuration scanned with bounded known-secret signatures; core Apache-2.0 boundary audited | NOT RUN; working tree still contains authorized uncommitted build work |
| G1 | Core52 short tests; strict typing; governor18 tests; mathematical invariants covered by existing suites | NOT RUN; full slow statistical/property rerun required |
| G2 | Actual synthetic32-input three-head INT8 fixture exported and verified;12 bundle adversarial tests | NOT RUN for pretrained release candidate; fixture is not pretrained model evidence |
| G3 | PhaseB53 API tests,200 bounded cross-tenant read/write tasks,0004 up/down/up,15 isolated security checks | PhaseB PASSED; final source-frozen rerun NOT RUN |
| G4 | Production14-page Next build/traces, six functional workspaces,12 axe scans at1440 light/320 dark with0 violations, live SDK/MRTR | PhaseC PASSED; final source-frozen rerun NOT RUN |
| G5 | Three sequential Linux image builds; live capped Compose/PgBouncer stack and100 pooled transactions | PhaseD PASSED; final rerun NOT RUN |
| G6 | Restore negative control plus external tombstone replay; same-code configuration cutover failure/rollback | PhaseD scoped PASSED; cross-version/schema rollback NOT VERIFIED |

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
