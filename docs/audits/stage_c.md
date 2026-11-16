# Phase 2 Stage C: native production runtime

Executed 2026-11-14 on Windows, under `scripts/gpu_guard.py` and exclusive
`.runtime/heavy_job.lock`. No Compose image builds or ML training overlapped.
Audit PostgreSQL16 retained its384MiB RAM/512MiB memory+swap/oneCPU cap,
64MB shared buffers and80 connections from Stage B.

## Final executed receipt

```powershell
.venv/Scripts/python.exe scripts/gpu_guard.py -- .venv/Scripts/python.exe scripts/runtime_stage_c.py
```

**Exit0.** Native setup preserves `resolveit_demo`, migrates to0004, keeps private
keys out of output, and provisions two separate synthetic reviewer subjects.
One `uvicorn --workers 1`, one clarification sweep worker, and already-built
`next start` ran on loopback. No `next dev` used.

- Official installed MCP SDK initialize/initialized/tools-list/tools-call passed
  against live HTTP. Negotiated2025-11-25 adapter persisted a synthetic incident.
- Strict2026-07-28 enterprise request performed genuine two-round-trip elicitation,
  accepted source citation, then returned DEFER because answer policy is not
  independently certified. Replay returned the same incident/outcome. Final run
  encountered deterministic exploration on attempt12; no route certificate was
  fabricated to obtain an ASK or ROUTE result.
- Headless Chromium used one browser/context and renderer-process-limit1 with
  disable-dev-shm-usage. Windows Chromium crashed with `--single-process` on the
  first attempt; removing that unsupported execution profile fixed the crash.
- Axe WCAG2A/2AA/2.1AA: **zero violations across12 views**, six workspaces at
 1440px light and320px dark. No horizontal overflow in those views. This automated
  result is not proof of all WCAG requirements or every possible application state.
- Functional browser checks passed: Database intake route, connected CSV analysis,
  MCP initialization/discovery/submission, interactive risk-gate explorer, settings
  optimistic save, live subject erasure and subsequent ERASED state, two separate
  encrypted credential logins and blind independent annotation submission.
- Persisted annotation verified: label_count2, synthetic_labeled status, exported
  `human_on_synthetic` provenance, no human_gold promotion. These are automated
  test identities/labels over synthetic data, not human annotation evidence.
- API, worker and Next children cleaned in finally. Fresh socket checks after the
  final run confirmed no listener on127.0.0.1:8000 or:3000. PostgreSQL remains
  available for Stage D; no unrelated user processes were terminated.

Machine-readable receipt: `artifacts/stage-c/receipt.json`. Screenshots:
`artifacts/stage-c/{1440,320}-{intake,review,bounce,evaluation,mcp,settings}.png`.

## Real measured latencies

| Measurement | Result |
| --- | --- |
| First incident POST after native process readiness |239.9781ms |
| Warm incident POST,30 timed requests, p50 |203.04315ms |
| Warm incident POST,30 timed requests, p95 |255.62114ms |
| CPU ONNX session load plus first inference |10.3239ms |
| Warm ONNX inference,200 warmups then200 timed, p50 |0.03045ms |
| Warm ONNX inference,200 warmups then200 timed, p95 |0.046305ms |

The first API ticket is a cold application request after readiness, not a freshly
booted OS/database. ONNX uses one intra-op and one inter-op CPU thread. The model
is the existing three-head **synthetic linear fixture**,32 numeric inputs; these
numbers do not describe pretrained multilingual text inference or its latency.

Post-run safety sample: physicalRAM70.1%,available4837.99MiB, true Windows
commit47.295%,swap1.5%,GPU51C,VRAM8.415%. Not a measured peak. Parent governor
remained active throughout the entire child tree; no hard-limit stop occurred.

## Real defect found and fixed

Production Next constructs an internal localhost URL while browser Host can be
127.0.0.1. Comparing browser Origin with `request.nextUrl.origin` incorrectly
rejected same-origin demo mutations403. Confirmed live error was `Origin denied`.
Demo comparison now uses the already-validated loopback Host and URL protocol;
production still requires configured canonical HTTPS origin. Regression asserts
internal-localhost/Host127 success and mismatched browser Origin rejection.

Fresh targeted middleware tests5passed; TypeScript/ESLint passed. Rebuilt full
production Next successfully, all14 pages and trace collection, compilation6.1s,
before rerunning the live checks. Harness Ruff passed, strict mypy passed2files.

Stage D and pretrained Stage E were not started by this specialist. Real tenants
remain shadow-gated; external Jira/A2A/cloud and managed backup erasure claims
remain separate release requirements.
