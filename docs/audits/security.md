# Isolated security gatekeeper audit

Review date: 2026-11-14. Baseline b5b8612 plus uncommitted concurrent build.
Scope: protocol/auth/tenant SQL/review provenance/worker/billing/web proxy. Production
code read-only for this role. Findings below describe inspected snapshots; writer
fixes require fresh verification before closing a finding.

## Findings delivered to writers

| ID | Priority | Evidence | Required behavior |
| --- | --- | --- | --- |
| S01 | High, calibration validity | `routes/workspaces.py:list_review` accepts caller `blind=false`, exposes model suggestion, and has no immutable exposure record. `submit_label` can promote two labels to gold, including calibration/frozen-test audit splits. | Enforce blind independent annotation on audit splits; record/exclude model or peer exposure from certification/test. Blinding must be server-enforced, not a checkbox claim. |
| S02 | High, privacy | `apps/worker/resolveit_worker/runner.py:sweep` still uses `log.exception`. Exceptions may include SQL bind values and raw text. | Log safe error category and IDs only; injected-payload regression must pass. |
| S03 | High, billing correctness | `delivery.py:settle_zero_bounce` treats no recorded bounce as zero bounce after72h without connector observation/watermark coverage. Connector is not active. | Fail closed unless connector observation is complete across full window. Disabled/helper-only status must remain explicit. |
| S04 | Medium, availability | MCP calls `request.json()` without byte ceiling; BFF routes read entire request body before upstream validation. Authentication has no connection/rate budget. | Bound request bytes before decoding and enforce gateway/app request budgets before public deployment. Domain field limits alone do not bound JSON allocation. |
| S05 | Medium, browser session boundary | Production encrypted session originally used generic cookie name, allowing sibling-domain cookie tossing with an attacker's valid session. | Production `__Host-` prefix, Secure, Path=/ and no Domain. Root repaired source. |
| S06 | Medium, login request allocation | Initial session login checked Content-Length but parsed unbounded JSON if header absent/forged. | Streamed2048-byte cap before JSON decoding. Root repaired source. |
| S07 | Protocol correctness | MCP2026 server/discover omitted required ttlMs/cacheScope. | Exact official generated wire schema validation. Backend repaired source; regression added. |

Existing deployed-scope blockers remain: no production browser OIDC/tenant sessions;
local key wrapper has no backup-wide destruction guarantee; no live Jira/A2A
interoperability evidence; pretrained multilingual and human frozen-test quality
must not be inferred from synthetic fixture results. These are not newly invented
security claims: master plan already gates public release on them.

## Independent checks

- Read canonical AGENTS, master plan, checkpoint, MCP transport/state/idempotency,
  auth, settings, tenant session boundaries, forced-RLS migrations0003/0004, review,
  delivery/outbox, encryption, browser middleware and scoped BFF forwarding.
- Added `tests/security/test_adversarial.py`: malformed signed state and credentials,
  malformed JSON-RPC, denied Origin, uncited answers, worker injected-payload log test.
- No-DB security suite completed:8 passed,1 failed in11.38s. Failure demonstrates
  S02: worker emits injected exception payload. Collection also emitted Windows
  fatal exception0x8007000e in platform WMI query while SQLAlchemy imported;
  process continued. Root notified of host pressure; avoid concurrent heavy jobs.
- Own test Ruff import ordering repaired; final Ruff check pending next gate.
- `npm audit --json` exit1:13 findings (1high,10moderate,2low). High PostCSS under
  `next/node_modules/postcss`; security advisories include
  [arbitrary source-map file read](https://github.com/advisories/GHSA-6g55-p6wh-862q),
  [incomplete source-map fix](https://github.com/advisories/GHSA-fxqj-rqcc-2cmp),
  and [minimatch glob amplification](https://github.com/advisories/GHSA-g3hv-75wg-m249).
  Scope is installed dependency graph, not proof these code paths are reachable
  through this app. Writer notified; avoid unreviewed major `audit fix --force`.
  Python `pip-audit --local --format json --progress-spinner off` exit0: no known
  vulnerabilities reported in installed third-party packages. Local ResolveIT API
  and core packages skipped because not found on PyPI. This checks advisory
  databases at scan time, not source-code security or future vulnerabilities.

## Fix verification checkpoint

- S02 fresh isolated suite:9 passed in3.72s; worker log canary now passes.
- S01 source now records model/peer exposure under trusted human identity across
  review/incident/MCP surfaces and excludes exposed audit annotators; database
  behavior/race checks pending final PostgreSQL run.
- S03 source now requires trusted connector coverage from route time through72h;
  app cannot advance observation watermark. Database boundary tests pending.
- S05/S06 source rechecked: production `__Host-resolveit_session`, separate local
  cookie, HttpOnly/Secure/SameSite=Strict, streamed login body cap independent of
  Content-Length. API credentials are revalidated each downstream request.
- SDK gate script prepared, Ruff and strict mypy passed. It checks loopback target
  and synthetic evaluation provenance before a real official SDK2.3
  initialize/list/call write. Live endpoint execution pending runtime readiness.
- S07 exact official2026 generated discovery-wire-model regression passes;
  protocol/log suite now10 passed in6.20s.
- S04 API RequestLimits middleware now reads actual ASGI stream bytes before JSON,
  caps ordinary requests128KiB and CSV8MiB, uses absolute10s body deadline and
  limits32 active requests per process. Five independent ASGI tests passed in1.55s:
  absent/forged Content-Length oversize413, exact chunk replay,429 before body
  consumption with Retry-After, capacity recovery and disconnect cleanup.
  Distributed/gateway quotas and any remaining BFF pre-upstream allocation are
  separate availability gates.
- Runtime role reports RAM94-98%, above latest user90% ceiling. Audit Docker
  stopped again; no live API available for SDK, database stress or browser checks.
  Do not turn this resource block into a runtime pass.

## Remaining execution gates

Fresh isolated security tests; 200-coroutine tenant probe against PostgreSQL16;
1000-event Jira echo-guard test; migration up/down/up final revision; official MCP
SDK initialize/list/call; dependency and secret scans; web behavior+axe at desktop
and mobile; failure-path log canaries; full final lint/types/tests. Prior writer
test counts are useful checkpoints, not isolated final approval.

No production-grade or vulnerability-free claim is supported by this report.
