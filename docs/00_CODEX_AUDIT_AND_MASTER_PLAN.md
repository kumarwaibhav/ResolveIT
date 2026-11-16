# ResolveIT audited master plan

Audit baseline: `b5b8612572a00c875f0a816a0620686dff851e16`; review date 2026-11-14 (Asia/Calcutta). This is a testable design and release contract, not a claim of a flawless or production-ready system. Implementation and executed evidence live in `BUILD_STATE.md`.

## Independent handoff verdict

Keep the monorepo and existing pure-Python contracts/text/math foundation. Refactor correctness/security gaps before increasing deployment scope. Add an independently tested standard adapter beside the enterprise profile. Complete missing product surfaces and operations with honest synthetic execution while collecting human gold.

The handoff transcript is present at `docs/legacy_claude_handoff.txt` (68,222 bytes at audit). It repeats `2026-07-28` from the original request (lines 28, 280–282); the final README explicitly admits absent SDK verification. Root's subsequent source verification establishes that this revision exists: the defect hypothesis is compatibility/negotiation, not an invented date. Handoff lines 675–679 acknowledge threshold lockout and skipped training. These are evidence of unresolved work, not release evidence.

| Commit | Audit disposition |
| --- | --- |
| `eef6965` core/contracts/text/gate | KEEP structure; REFACTOR cold-start, validation, empty-set policy and risk certification; VERIFY multilingual offsets/masking empirically |
| `130f614` API/RLS/encryption | KEEP persist-first and tenant transaction pattern; REFACTOR tenant-consistent FKs, deploy auth/key lifecycle, schema migrations |
| `03ccf28` MCP/worker | KEEP signed state and bounded recovery concept; REPLACE version-coupled transport; REFACTOR atomic idempotency and direct worker lock connection |
| `db658ab` idempotency typo | KEEP bugfix; insufficient to resolve duplicate-call race |
| `662d6de` web | KEEP generated types, client meter and evidence UI; REFACTOR shared-key public proxy; BUILD remaining workspaces |
| `b5b8612` lint/closure fix | KEEP; lint is not runtime/security certification |

## Audit decisions and release blockers

1. **Cold-start lockout: confirmed.** `ChannelCosts.rho=(answers+1)/(asks+2)`. Ask beats defer only when `rho*(R_now-R_after) > c_ask+(1-rho)*c_ghost`. In shadow mode every posterior route is forbidden, so `R_after=R_now=c_def`; no positive ask cost can win, regardless of response prior. Use configurable warm Beta(4,2) plus explicit deterministic 5% exploration on eligible ambiguous critical slots outside 10% no-ask holdout. Record exploration reason/propensity; never let exploration certify routes.
2. **Threshold lockout: confirmed design limitation.** Exact fixed-sequence test stops at its first failure. It protects a fixed sequence but can be underpowered. Do not trade correctness for uncorrected adaptive Wilson intervals. Retain exact baseline; add finite-sample empirical-Bernstein certification with a predeclared grid/queue error budget or independent candidate-selection/certification split. Wilson is diagnostic only unless separately justified. Certify actual cost-minimizing action after every routing eligibility condition, separately per destination queue. Unsupported queues remain shadow. Repeated time windows need an explicit spending schedule or fresh frozen certification event.
3. **Calibration split leakage: refactor.** Synthetic bundle temperature uses a separate scaling split, but conformal fit and selective confidence search share generated samples. New bundle pipeline separates training, temperature scaling, conformal fitting, policy selection, risk certification and untouched evaluation. Human-gold frozen test is never tuning input. Coverage labels identify pooled versus supported class-conditional guarantees.
4. **Empty-set contradiction: resolve strictly.** Legacy `decide` can ASK on empty conformal set and corresponding test permits it, despite doc invariant. New invariant: immediate DEFER `no_conforming_team`, no exploration override.
5. **Missing trained model: confirmed.** `bundles.py` has one-dimensional pooled input and manually weighted linear head. Build three-head student/teacher interfaces, reproducible LoRA training/export, ONNX opset 17 INT8 runtime and bundled calibration. Synthetic smoke model proves mechanics only; does not prove mDeBERTa/LoRA training or enterprise accuracy.
6. **MCP interoperability: add compatibility adapter.** Existing endpoint requires method/name headers and revision metadata, lacks the legacy initialize/initialized lifecycle and has not met an official SDK. The revision itself exists; older SDK interoperability still needs a dual-mode adapter. Support standard `2025-11-25` lifecycle alongside the strict `2026-07-28` enterprise profile, with independent SDK evidence for each claim. A2A requires independently sourced contract and client interoperability evidence.
7. **MCP idempotency: confirmed race.** `_call_tool` checks mapping, commits `submit`, then inserts mapping `ON CONFLICT DO NOTHING`. Concurrent calls can persist duplicates; body digest also collapses legitimate identical later incidents forever. Use caller-provided operation key with bounded retention, atomic reservation/row lock, canonical request digest conflict detection and durable response recovery. Bind tokens to credential identity, tenant, tool, arguments, incident, expiry and policy/bundle. Validate every signed payload type. Substring citation proves presence, not semantic entailment; uncertain assertions remain human-gated.
8. **Tenant relationships: harden.** ENABLE/FORCE RLS and NullPool are sound foundations, but standalone `incident_id` FKs do not enforce same-tenant parent/child ownership. Use composite `(tenant_id,id)` unique constraints/FKs, including parent links. Test inserts and updates against other tenants, not reads alone. Narrow definer roles/functions and bound cross-tenant discovery limits.
9. **Web auth: release blocker.** Next server routes proxy a shared server API key without browser session authorization. Production deployment grants anonymous visitors that key's capabilities. Restrict demo to loopback synthetic tenant; add verified OIDC sessions, role/tenant checks and CSRF/origin controls before external exposure.
10. **Crypto-shredding: correct claim.** AES-256-GCM per-incident keys/AAD and blind HMAC indices are useful. Local HKDF wrapper is development only. Deleting live wrapped keys cannot erase backups containing those keys and the master. Managed KMS lifecycle, restore tombstone replay, derived-copy cleanup and retention procedures are release requirements.
11. **Logging: verify rather than trust comments.** Worker `log.exception` may render exceptions containing SQL bind parameters. Use safe error classes/codes and IDs only; scan captured failure-path logs with planted text/PII canaries.
12. **Missing ops/product: confirmed.** Legacy README lists no outbox, Jira connector, billing ledger, review, bounce analyzer, evaluation, settings or deployment. A page shell is not a connected backend workflow. Every action requires tenant authorization, persistence, loading/error/empty states and E2E evidence.

## Locked architecture

Use PostgreSQL 16 as transactional source of truth; avoid introducing Redis/Kafka until measured need. FastAPI hosts domain services with thin REST/MCP/A2A adapters. Next App Router provides six workspaces: intake, review/annotation, bounce analysis, evaluation, handoff/explorer, settings/privacy. Worker uses inbox/outbox with `FOR UPDATE SKIP LOCKED`, bounded retries, lease recovery and dead-letter visibility. Tenant transactions are independent; external calls never hold DB locks.

Bundle loading verifies complete SHA-256 manifest, schema/model/tokenizer compatibility and provenance before use. Missing or invalid bundle fails closed into real-tenant shadow. Route eligibility combines certified queue threshold, conformal support, mapped queue, critical-slot consistency and cost decision. Security triggers bypass ordinary queue recommendation into explicit security handling; they never imply arbitrary calibrated probabilities.

Review has two independent annotators with blinded model suggestions, conflict adjudication and immutable revision provenance. Agreement metrics display support and undefined states; no fabricated kappa/alpha for empty or degenerate labels. Incident/person/time grouping prevents split leakage. Training corrections stay training; random pre-decision audit collection feeds unbiased certification and frozen tests.

Jira loop breaking layers: authenticated timestamped delivery, delivery-ID inbox dedupe, source/correlation marker, normalized semantic-change check and bounded version/hop guard. State mutation and outbox insert commit together. Delivery is at least once; consumers/effects are idempotent. Billing waits a complete 72-hour observation window, excludes bounce/defer/erased or incomplete outcomes according to versioned commercial policy, and appends tenant-serialized canonical hash-chain entries. Hash chaining detects tamper only with independent anchoring and restricted append permissions.

## Staggered execution and exit gates

| Stage | Scope | Exit evidence |
| --- | --- | --- |
| 0 | inventory, commit/handoff audit, baseline, hardware/tool constraints | Audited docs, secret scan scope, test baseline and known blockers recorded |
| 1 | gate/math/contracts and defensive input validation | Math properties, empty-set/holdout/exploration regression tests, risk-bound simulations and strict static checks |
| 2 | Alembic/RLS/crypto/auth/dual MCP | Migration up/down/up on disposable PG16; 200 concurrent tenant probes; SDK initialize/list/call; malformed/replayed state tests |
| 3 | inbox/outbox/Jira/ledger | Crash/retry/concurrent worker tests; 1,000 delivery echo storm; deterministic 72h boundary and chain verification |
| 4 | ML/export/calibration and annotation | Guarded training, ONNX FP32/INT8 parity and runtime smoke, manifest validation; honest provenance; independent labels to fixed splits |
| 5 | six enterprise workspaces | Connected API workflows; keyboard/mobile/reduced-motion; WCAG 2.1 AA axe and behavior E2E |
| 6 | Compose/PgBouncer/seed/release ops | Clean bootstrap; readiness probes; tenant synthetic fixtures; backup/restore/erasure test; measured warm/cold p50/p95 and blue/green rollback |
| 7 | independent gatekeeper release audit | Secret/dependency checks, all required gates executed, artifacts reviewed, known limitations assigned; real route unlock only on supported human evidence |

Stages can overlap only on independent file contracts. Four available agent slots require waves across six specialist roles; gatekeeper never edits writers' production code. Principal resolves conflicts once using measured correctness and operational simplicity.

## Honest completion policy

No universal zero-bounce or 100% production claim is supported by a code-only audit. Report verified behavior and remaining blocked gates precisely. Synthetic runs may expose smoke metrics with permanent dataset badges; product performance metrics require untouched human test data. Missing GPU/Docker/Postgres/KMS/labels remains explicit evidence gap, never silent pass. Checkpoint every completed stage in `BUILD_STATE.md` so execution resumes from concrete artifacts.
