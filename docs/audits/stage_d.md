# Stage D — sequential Compose/PgBouncer runtime rehearsal

Rehearsal executed 2026-11-14 Asia/Calcutta; final evidence and cleanup verified
2026-11-15. **Local Stage D gates passed.** This is a synthetic, loopback deployment
rehearsal, not approval for external production traffic.

## Execution and artifacts

Applied `a-team:verification-before-completion` from the installed
`a-team/1.4.1/skills/verification-before-completion/SKILL.md`: claims below are based
on executed commands and inspected results. No optional skill inventory was loaded.

Images were built one at a time under `scripts/gpu_guard.py` and its exclusive OS
mutex, after stopping the preserved `resolveit-audit-pg` container. No native Next,
Playwright or training job ran concurrently.

```powershell
.venv/Scripts/python.exe scripts/gpu_guard.py -- docker compose build api
.venv/Scripts/python.exe scripts/gpu_guard.py -- docker compose build --build-arg NODE_HEAP_MIB=1536 web
.venv/Scripts/python.exe scripts/gpu_guard.py -- docker compose build pgbouncer
.venv/Scripts/python.exe scripts/ci_gates/stage_d.py
```

All three image builds exited 0. Linux web build compiled in 13.1s and completed
all 14 static pages and trace collection; its `npm run build` step took 41.9s.
Image export/unpack completed; compilation alone was not treated as a build pass.

| Image tag | Immutable image identity inspected after rehearsal |
| --- | --- |
| `resolveit-api:stage-d` | `sha256:d2dad40f9dfeb74e5b4d625fb44d79b8006454c6e998e00f9fd2882541f73a75` |
| `resolveit-web:stage-d` | `sha256:057074a4a98aeafaa81bdaceac386d4656d0798b8e3a7c219d0a7f52257e3e71` |
| `resolveit-pgbouncer:stage-d` | `sha256:e80212b024d5242f580af506e38cb2b825bf174e8014227b8ade9efea24063d1` |

API/setup/worker share the explicitly named API image. `up --no-build` prevents
implicit parallel builds. PgBouncer installed version was **1.26.1**.

The guarded runtime/restore/rollback script exited 0 in **53.4323s**. Exact receipt:
`artifacts/stage-d/receipt.json` (ignored). Backups contain private wrapped keys and
credentials; the ignored artifacts directory must remain private and unpublished.

## Memory and runtime checks

Five steady service caps sum to **1,344 MiB**, plus Docker/WSL overhead and a bounded
one-shot setup service. These are container limits, not a measurement of total host
or WSL memory consumption.

| Service | Limit | Verified stopped state after rehearsal |
| --- | --- | --- |
| PostgreSQL 16 | 384 MiB | exited, no OOM kill |
| PgBouncer | 64 MiB | exited, no OOM kill |
| API | 384 MiB | exited, no OOM kill |
| Worker | 256 MiB | exited, no OOM kill |
| Production Next server | 256 MiB | exited, no OOM kill |

PostgreSQL uses 64MB shared buffers and 80 maximum connections. Published API and
web ports bind loopback only. Stack startup completed; PostgreSQL and API health
were healthy, authenticated `/v1/me` verified the fixed synthetic tenant, and the
production browser proxy/evaluation endpoint returned success. No real tenant was
used for mutation.

| Telemetry | Before runtime | After runtime, before stack stop |
| --- | --- | --- |
| Physical RAM | 76.8% | 77.5% |
| Available RAM | 3,758.38 MiB | 3,648.45 MiB |
| Windows commit | 51.3285% | 51.4925% |
| Swap usage | 1.6% | 1.6% |
| GPU temperature | 53°C | 53°C |
| VRAM | 8.83% | 9.78% |

These are sampled endpoints, **not peak measurements**. The governor monitored the
heavy child throughout. No safety limit was bypassed or unrelated process stopped.

## Actual PgBouncer and direct-worker evidence

- API's effective connection URL was verified to target PgBouncer. An authenticated
  tenant transaction read exactly its tenant; current role was neither superuser
  nor BYPASSRLS. The transaction-local tenant setting was absent after return.
- **100 real pooled transactions** ran through the shipped SQLAlchemy/asyncpg
  implementation. Maximum visible prepared-statement count was **1**, rather than
  accumulating UUID-named statements indefinitely.
- Running pool configuration was verified as `pool_mode = transaction`.
- `server_reset_query_always = 1` intentionally runs `DISCARD ALL` after transaction
  return. PgBouncer normally skips reset queries in transaction mode; this explicit
  policy fits our NullPool, disabled statement caches, UUID prepared names and
  transaction-local tenant state. See [official reset-query configuration](https://www.pgbouncer.org/config#server_reset_query_always).
- Worker's effective URL targeted PostgreSQL directly. The actual
  `Database.leader_lock` implementation was tested with an isolated rehearsal lock
  ID: first session acquired, second session was excluded, and acquisition succeeded
  again after release. This checks direct session-lock behavior without stealing the
  running sweep's own leader lock.

## Backup / restore / external-tombstone drill

1. Created one uniquely identified synthetic incident through the live API; confirmed
   its wrapped incident key existed.
2. Captured a PostgreSQL custom-format backup **before** erasure. SHA-256:
   `df4ccb29cd05e0903e7215407be69ded383c5a7ee645cb816cde73da18a270da`.
3. Called the authenticated privacy-erasure endpoint and confirmed exactly one
   incident was erased. Persisted its tenant/incident tombstone outside the backup.
4. Restored into newly created disposable database
   `resolveit_restore_414d192e6442`, with no public application connected to it.
5. Negative control confirmed the pre-erasure backup restored the wrapped key.
   **Live key deletion therefore does not erase historical backups.**
6. Replayed the external tombstone transaction before exposure. Confirmed ERASED
   state; no incident key, frames, questions, review labels/items or subject index;
   raw/masked text and nonce were null. All 20 tenant tables retained ENABLE/FORCE RLS.

Original Compose volume and audit database were preserved. Disposable restore DB
was retained privately for evidence. Production needs managed key revocation,
durable authenticated external tombstone retention and enforced restore quarantine;
this local scripted drill does not prove those cloud/organizational controls.

## Local blue/green rollback scope

Started a separate bounded green web container using the **same immutable image**
as blue but an intentionally broken API-origin configuration. A local proxy switched
traffic blue → green, observed the authenticated evaluation smoke fail, switched
back to blue, and observed recovery. Green was stopped; final cleanup removes its
task-owned stopped container. Proxy/listener threads were shut down.

This passes a **same-code deployment-configuration cutover/rollback** rehearsal.
It does not claim compatibility with an older application image, schema downgrade
under real traffic, cloud load-balancer rollback, or a cross-version migration.
Those distinctions must remain visible in the final release scorecard.

## Final verification and cleanup

- Ruff passed for `runtime_stage_d.py` and `ci_gates/stage_d.py`.
- Strict mypy passed both source files.
- `docker compose stop` completed in the rehearsal's `finally` cleanup.
- Final inspection confirmed all five service containers stopped, no OOM kills,
  and no listeners on 8000/3000/3001/3002. No volume was deleted or rekeyed.
- Docker Desktop was stopped for Stage E memory/thermal isolation. All build and
  runtime heavy children exited; OS mutex released.

`production_authorized` remains **false**. Stage E training and final release
scorecard are owned by the coordinator and were not started during this stage.
