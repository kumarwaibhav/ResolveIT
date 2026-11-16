# Architecture audit evidence

Baseline SHA: `b5b8612572a00c875f0a816a0620686dff851e16`. Review date: 2026-11-14.

## Inspected evidence

- Enumerated all six commits and per-file change statistics with `git log --reverse --stat`; read root CLAUDE/README and targeted handoff sections for protocol, priors, selective-risk and skipped training claims.
- Directly reviewed contracts, calibration, EVSI gate, API pipeline/bundles/auth/settings/session, intake/erasure/MCP, worker, both SQL migrations, bootstrap roles, crypto module, web API proxy, contract exporter and legacy quality scripts.
- Code graph parsed 101 supported files with 1,194 nodes/4,391 edges and no parse errors. Python resolution indexed 47 files. This is structural coverage, not proof every file was manually security-audited.
- Graph found 14 resolved call sites to `decide`, including legacy test allowing empty-set ASK; `submit` is reached by REST and MCP. Changes to gate semantics require both paths plus finalization/recovery tests.
- No claim here that inherited tests were freshly executed; root/gatekeeper own executed validation evidence in `BUILD_STATE.md`.
- Known-signature secret scan read all 122 reachable git blobs plus local git configuration: zero GitHub/OpenAI/AWS-access/private-key/credential-URL matches. This bounded signature scan is not entropy scanning or proof that arbitrary credentials are absent. Values were never printed. No local author name/email was returned by `git config --local --get`; commits must wait for explicit local author configuration rather than invent identity.

## Finding inventory

| ID | Severity | Baseline evidence | Required disposition |
| --- | --- | --- | --- |
| A01 | Critical for public deployment | Shared-key Next API proxy, no browser session boundary | Loopback-only demo; production session/tenant auth |
| A02 | High | MCP precheck/submit/ON CONFLICT spans transactions | Atomic principal-scoped operation idempotency |
| A03 | High | Strict revision-specific headers and absent older SDK lifecycle | Dual-mode standard adapter + SDK tests; root verified 2026-07-28 exists |
| A04 | High | Live wrapped-key deletion described as erasing all backups | Correct claim; managed KMS and restore tombstones |
| A05 | High | Child references incident UUID without tenant equality | Composite tenant-consistent FKs and adversarial writes |
| A06 | High | Warm prior alone cannot make shadow EVSI ask | Explicit controlled exploration with holdout |
| A07 | High | Selective threshold fixed-sequence first-failure lockout | Sound per-queue independent/multiplicity-safe certification |
| A08 | High | No trained/exported INT8 model or bundle registry | Full reproducible pipeline, permanent provenance badges |
| A09 | Medium | Empty-set ASK conflicts with documented immediate DEFER | Strict fail-closed invariant/regression |
| A10 | Medium | Worker logs exception stack; bound values not redacted | Safe error codes + injected-text log test |
| A11 | Medium | Pending finalization uses current tenant bundle | Resolve immutable original bundle through rollout |
| A12 | Medium | Signed payload fields not fully typed; citations substring-only | Defensive token validation; conservative agent assertions |
| A13 | High for release | Missing UI/ops/inbox/outbox/ledger/migrations features | Stage-specific live acceptance evidence |

Findings describe baseline behavior. Implementation may change during concurrent work; root must mark verified fixes against final diff. Do not reuse this baseline inventory as proof of current unresolved or fixed status without checking.
