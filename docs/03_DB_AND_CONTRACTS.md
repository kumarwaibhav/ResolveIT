# Database and contract decisions

Pydantic v2 schemas under `packages/resolveit-core/resolveit_core/schemas/` are authoritative. Generate OpenAPI and TypeScript after contract changes; fail CI on drift. This document specifies invariants rather than copying shapes.

## Persistence rules

- Every tenant-owned row carries `tenant_id` and ENABLE/FORCE RLS. App role is neither owner nor BYPASSRLS; missing tenant context returns no rows and rejects writes.
- Child links use `(tenant_id, parent_id)` to a matching unique `(tenant_id,id)` key. RLS alone does not enforce referential tenant equality. Null parent links remain allowed only where explicitly modeled.
- Tenant transactions use verified UUID credentials, `set_config(..., true)`, `NullPool` and disabled prepared caches. Narrow SECURITY DEFINER auth/discovery functions have fixed search paths, revoked PUBLIC execution and bounded output.
- Alembic owns schema versions. Existing SQL becomes audited initial revisions; upgrade/downgrade/re-upgrade is tested against disposable PG16, including RLS flags/grants/functions. Do not retroactively edit an applied migration.
- Incident state transitions lock/version rows. At most one question closes once. Finalization resolves original `bundle_id`, not current tenant default. Bundle rollout retains versions needed by pending questions.
- Client operation keys are tenant/principal scoped and bind canonical request digest. Duplicate same-key requests recover canonical incident; different payload reuse returns conflict. Reservation and incident creation are atomic or recover through durable state.

## New artifact contracts

Inbox: provider, tenant, delivery ID, payload digest, received timestamp and processing state; dedupe via unique constraint. Outbox: tenant, aggregate/version, effect key, safe payload/reference, attempt schedule, lease and dead-letter state. External text payloads follow encrypted retention rules.

Review: independent annotator IDs, label revision, provenance, audit sampling propensity, blind/revealed state, adjudication and immutable split assignment. Agreement uses only overlapping comparable records and states undefined results explicitly.

Bundle registry: immutable manifest hash, per-file checksums, schema/model/tokenizer versions, source provenance, split hashes, fit metadata, queue certification support/bounds and activation state. No route when artifact verification or queue support fails.

Billing: append-only versioned outcome observations and tenant-serialized ledger chain. Canonical bytes include sequence, tenant, event/version, eligibility window and previous digest. Late bounce produces explicit reversal, never history mutation. Independent anchors/restricted grants are needed for meaningful tamper detection. No PII in ledger.

Erasure: authorized request, irreversible confirmation, idempotent job, destroyed/revoked data-key reference, derived-copy cleanup and persistent restoration tombstone. Backups cannot be served before tombstone replay. HMAC subject indices need retention/minimization review; they remain pseudonymous identifiers, not anonymous data.

## Boundary validation

Probability vectors have twelve finite nonnegative entries summing to one; calibration class arrays align with canonical team order; thresholds/costs have finite legal ranges. Span offsets are bounded, ordered raw code points and convert once to UTF-16 for browser. Signed tokens validate type/size/expiry/principal/tool/digest/version before use. JSON-RPC notifications do not receive normal request responses; parse/validation/tool failures use appropriate protocol semantics. Enterprise citation spans must reference original text; source presence alone is not proof of claimed meaning.
