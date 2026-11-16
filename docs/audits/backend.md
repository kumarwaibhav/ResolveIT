# Backend zero-trust audit and delivery checkpoint

Scope: original commits through b5b8612; updated 2026-11-14. No production-readiness claim.

## Verified findings and changes

- KEEP forced PostgreSQL RLS, credential-derived tenants, transaction-scoped tenant settings, NullPool, AES-256-GCM incident keys, persist-first intake and row-locked question closure.
- REFACTOR MCP compatibility: live official documentation confirms **2026-07-28 is real**, not fabricated. Existing strict MRTR profile remains. Added stateless 2025-11-25 initialization, initialized notifications, ping, tools/list and tools/call. Legacy clients receive complete results; unresolved clarification stays human-gated.
- FIX malformed signed state expiry/UUID crashes, token size bounds, API-key identity binding and exact quote checks. Agent REST answers cannot bypass citation checks; MCP answers always carry agent_asserted provenance. Quote matching is conservative syntactic support, not semantic entailment certification.
- FIX concurrent MCP creation: transaction advisory lock, incident and deduplication claim commit atomically. Deduplication now requires explicit `_meta["resolveit/idempotencyKey"]`; distinct unkeyed calls never merge merely because text matches. Key reuse with different arguments fails.
- FIX tenant-inconsistent foreign references with composite incident foreign keys. RLS alone did not close this write-integrity hole.
- FIX intake/erasure race using shared incident row locks. Correct misleading backup shredding claim: backups retaining wrapped keys remain decryptable.
- ADD reversible Alembic revisions 0001-0003, reusing audited SQL statement-by-statement. Migration credentials are separate from application credentials. alembic_version is operational metadata, not tenant data.
- ADD transactional route outbox and hash-chained billing events. Application UPDATE/DELETE of ledger and cascade deletion through incidents/tenants are revoked. Fenced delivery leases, bounded retry and dead-letter state use an injected transport; receiver idempotency is still required for at-least-once delivery.
- ADD Jira guard primitives: raw-byte HMAC, durable delivery/body dedupe, integration actor exclusion, origin marker exclusion, stale/no-op assignment exclusion. No external Jira connector is configured or claimed complete.
- ADD 72-hour settlement primitive excluding synthetic tenants and recorded bounces. Production settlement needs a complete, monitored external reassignment event feed and independent immutable chain-head anchoring.

## Executed evidence at checkpoint

- PostgreSQL 16 integration: `RESOLVEIT_TEST_SKIP_BOOTSTRAP=1 python -m pytest -q -k 'not 200'` from apps/api: **42 passed, 1 deselected**, 44.92s. Includes 1,000-event Jira echo guard and 12-concurrent keyed MCP creation.
- Strict mypy: **20 source files, no issues**. Ruff API/enterprise/worker scope clean after formatting.
- Fresh disposable database: Alembic **upgrade head -> downgrade base -> upgrade head**, revision **0003** verified after both upgrades. Rehearsal uses a disposable audit database; destructive downgrade is not a production rollback plan.
- 200-coroutine stress test deliberately not run at this checkpoint because host RAM exceeded hardware governor limit.
- Core post-answer calibration changes arrived after this checkpoint; rerun integration against final core before claiming current green status.

## Remaining release gates

- Authenticated individual human identity for annotation; API keys alone do not prove independent people.
- External Jira field mapping, issue mapping, actual transport, credentials, webhook endpoint and integration/sandbox tests.
- Outbox retry/fencing failure-injection coverage, late bounce credits, positive 72-hour settlement/window-boundary tests and immutable external chain-head anchoring.
- Managed KMS wrapper, backup/key retention erasure policy and restore rehearsal.
- Full SDK client smoke test, production HTTP body/rate limits and operational alerting.

Sources verified live: [2025 Streamable HTTP](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports), [2025 lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle), [2026 Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http), [Atlassian webhook signature and delivery identifiers](https://developer.atlassian.com/cloud/jira/platform/webhooks/).

## Workspace stage: source implemented, runtime verification pending

Migration 0004 and `schemas/workspaces.py` add persistent review items, immutable split assignments, immutable independently enrolled human labels, third-person adjudication, settings, exposure history and a trusted connector completeness watermark. Database jobs stopped before this stage so the coordinator could free Docker memory; **0004 has not yet received a PostgreSQL upgrade/downgrade or integration pass**.

Endpoints:

- `GET /v1/me`: verified tenant/role, synthetic flag, human enrollment flag; no key or human UUID disclosure.
- `GET /v1/review?blind=true&limit=20&after=<uuid>`: max 50; cursor is the final incident UUID. Current human sees own label only; model/peer exposure flags are explicit.
- `POST /v1/review/enqueue`: legacy tickets enter training only. New incidents receive immutable split assignment in their persistence transaction, before inference.
- `POST /v1/review/{id}/labels`: all 11 slots required, identity comes from trusted `api_keys.human_subject_id`; duplicate keys for one human count once. A second independent matching annotation produces gold only for a real tenant; synthetic material remains `human_on_synthetic`.
- `POST /v1/review/{id}/adjudication`: third enrolled human with admin role, after two disagreeing immutable labels. They may inspect peers; prior model exposure blocks adjudication on audit splits.
- `GET /v1/review/agreement`: computed nominal team-label agreement, Cohen kappa for one fixed human pair, nominal Krippendorff alpha; undefined statistics remain null. Bounded to most recent 5,000 paired units.
- `GET /v1/review/export?split=training&limit=50&after=<uuid>`: admin-only, max 100, explicit provenance and split. Frozen-test data must stay outside training in the downstream dataset registry.
- `GET/PUT /v1/settings`: admin-only optimistic version check. Timezone updates apply immediately; saved queue/cost configuration explicitly remains `pending_connector_and_recalibration`.
- `GET /v1/evaluation`: actual current bundle/provenance and persisted gold counts; no invented frozen-test accuracy.
- `POST /v1/bounce/analyze`: bounded in-memory CSV with `ticket_id,assignment_group,timestamp`; timezone-aware ISO timestamps required; no retention. Ambiguous same-time conflicting assignments fail instead of inventing an order.

Independent gatekeeper fixes incorporated in source:

- S01: immutable model/peer exposure records cover review suggestions and authenticated REST/MCP incident outputs. Model/peer-exposed people cannot independently label audit splits; model-exposed adjudicators cannot adjudicate them. Review subjects come from trusted credential enrollment, never client payloads. Existing un-enrolled keys cannot produce human gold.
- S02: worker exception logs contain incident ID and exception class only; arbitrary exception strings, SQL parameters and tracebacks are excluded.
- S03: zero-bounce settlement requires a persistent verified observation watermark covering the full route-to-72h window. Watermark table starts empty and application credentials cannot advance it, so settlement remains disabled without a separately trusted completeness-verifying connector.

Additional release limitation: frame/annotation slot values are stored as JSONB and can contain user-entered personal information. Live erasure removes them; production backup privacy requires incident-key encryption of these payloads or an independently verified retention/backup erasure mechanism. No claim of backup-wide crypto-shredding applies.

Final static and database tests must include the final per-queue synthetic certificate policy and post-answer fail-closed behavior. Earlier 42-test evidence is a historical checkpoint, not verification of this new stage.

## Final source checkpoint and resource-blocked database verification

- Final API/enterprise/worker Ruff check with automatic import fixes: zero remaining errors. Strict mypy: **23 source files, no issues**.
- Independent gatekeeper executed **10 protocol/state/log tests** and **5 request-limit tests**, all passed. Request-limit tests cover forged/missing Content-Length, streamed oversize rejection, bounded replay, concurrency rejection before body reads, capacity recovery and disconnect cleanup.
- S04: ASGI ingress buffers actual streamed bytes before authentication/JSON decoding. Normal/MCP requests are capped at 128 KiB, bounce upload wire requests at 8 MiB (CSV content contract is independently tighter), body receipt has an absolute 10-second deadline, and per-process concurrency is capped at 32 with HTTP 429 and Retry-After. Distributed gateway quotas remain a production gate.
- Synthetic per-queue risk certification uses an independent generated risk draw and freezes membership, conformal-set size and the actual chosen-route delay <= defer-cost policy before certification. API gate receives queue thresholds; returned tau reflects the predicted queue. Post-answer distributions have no certificate and close as DEFER; tests now assert that behavior.
- Clarification tests choose fresh UUIDs that naturally hash into the fixed exploration group. They do not fabricate calibration or override the production gate. This removes probabilistic "try 80 times" failures after post-answer fail-closed changes.
- Guard refused the final database test process **before launch** at **94.0% RAM**, above the owner-approved 90% ceiling; GPU 57 C, VRAM 12.95%. No final database or migration-0004 pass is claimed. Historical 0001-0003 migration rehearsal and 42-test checkpoint remain valid only for that earlier state.
- The 1,000-event Jira result is a **PostgreSQL inbox/guard simulation**, not an external Jira webhook or live connector test. The 200-coroutine RLS stress test remains not run in this agent's final state.

Next required verification: under the resource governor, run the complete final API tests, disposable Alembic 0004 upgrade/downgrade/upgrade, native SDK smoke tests and workspace browser flows. Do not relax the 90% resource ceiling to obtain a green check.
