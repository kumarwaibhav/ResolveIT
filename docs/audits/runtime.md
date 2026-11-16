# Role 6 runtime audit

Date: 2026-11-14. Scope: Compose, images, pooler, local bootstrap and live verification.

## Executed evidence

- `docker desktop start` completed. Existing task-owned `resolveit-audit-pg`
  PostgreSQL16 container restarted on loopback54329; `pg_isready -U postgres`
  reports accepting connections.
- Audit container constrained to256MiB RAM,256MiB total memory/swap and one CPU
  using `docker update`. No unrelated container/app was stopped or changed.
- `docker compose config --quiet`: exit0 after current session-key/pooler additions.
- `ruff check scripts/bootstrap_db.py scripts/local_env.py`: passed.
- `mypy --strict scripts/bootstrap_db.py scripts/local_env.py`: passed,2 source files.
- Hardware telemetry after Docker startup initially97.8% RAM, then fluctuated
  89.3–90.2%. No image build started above owner-approved90% ceiling.
- After RAM rose94%, audit PostgreSQL and Docker Desktop were stopped again.
  Guarded Next production build with384MiB V8 heap started but governor stopped
  child at90.6% RAM during compilation. Exit1; this is not a passing build.
- Changed retry: disabled webpack build worker (root-owned config),256MiB heap;
  governor stopped at92.1% during compilation, exit1. No further unchanged retries.
- Single guarded native Next dev attempt refused before child launch at90.3% RAM.
  No preview, screenshot, browser journey or runtime latency claim is supported.
- `scripts/dev_native.py` added for prepare/api/web against task-owned local audit
  PostgreSQL. Ruff and strict mypy passed. Its database migration/runtime execution
  remains pending; it never drops an existing database or overwrites private keys.

## Changes

- Exclude nested `.env*` files from Docker context, preventing private web
  configuration being copied by `COPY apps/web/ ./`.
- Normalize PgBouncer entrypoint CRLF to LF during image build for Windows checkouts.
- Bound Next image build V8 heap to512MiB; Next worker count already one.
- Generalized bootstrap's database-owner DDL to the connected database, allowing
  isolated native-demo database without hardcoded production database name.
- Preserve direct worker PostgreSQL connection for session advisory locks;
  tenant API uses transaction-mode pooler with disabled prepared statement cache.

## Current verification limits

Compose syntax is not image-build or stack-boot evidence. Fresh API/pooler/web image
build, final Compose startup, pooler authentication under load, native live smoke,
SDK roundtrip, six-workspace browser/axe journeys, latency and rollback remain
pending. Backend writer owns sole DB-test slot before live runtime starts.
Database health probe proves server availability, not application readiness.
No native PostgreSQL binaries found in PATH or conventional Program Files path.

Local bootstrap is synthetic and loopback-published. Production requires managed
key lifecycle, HTTPS public origin and individual sessions, real connector
observability, independently calibrated human data and operational restore drills.

## Bundle integrity gate added

Fresh guard refused heavy launch at90.4% RAM; no unchanged build retried.
Added `scripts/verify_bundle.py` and12 adversarial tests. Checks required artifact
set, SHA256 digests, canonical manifest identity, optional trusted identity pin,
metadata provenance consistency, bounded regular-file reads, mutation detection,
path confinement, duplicate JSON keys, symlinks and Windows junctions. Model
hashing streams64KiB chunks rather than loading model into RAM. Metadata is parsed
from the same bytes whose digest was checked. No production routing is authorized
by this auditor; immutable release storage and trusted release identity are required.

Ruff passed; strict mypy passed1 source; pytest12 passed1.16s. Actual4-file synthetic
bundle verified with expected identity
`8be1d5cc616b46094b52e02ecf0566f1670aca7af7a4b9ede006c4c4b05b6d16`.
Result retains `label_source=synthetic_seed`, `production_authorized=false`.
