# Phase 2 Stage B — PostgreSQL/API integration gate

Status: **PASSED** on 2026-11-14. Scope: backend/database verification only. Stage A had finished; no Next build, browser, training or Stage C/D/E workload ran alongside these heavy jobs. All Stage B child processes have exited and the OS heavy-job mutex is released.

This gate establishes the behavior below on PostgreSQL 16 and the final backend source. It does not establish production ML quality, a live Jira connector, managed-KMS erasure, or completed browser workflows.

## Resource and database configuration

The latest owner-authorized headroom governor superseded earlier 90% notes: RAM 95.5%, at least 750 MiB available, commit/swap at most 88%, VRAM at most 85%, GPU pause at 75 C and stop at 78 C. Heavy jobs ran through `scripts/gpu_guard.py`, which holds `.runtime/heavy_job.lock` and monitors only the owned child tree. CPU math thread counts were bounded to two.

Docker Desktop started hidden. Only the existing task-owned `resolveit-audit-pg` container was configured/restarted. Its volume and existing databases were preserved. The migration rehearsal used its own disposable `resolveit_stage_b_audit` database; API fixtures recreate the explicitly disposable `resolveit_test` database.

Verified runtime configuration:

| Setting | Measured value |
| --- | --- |
| PostgreSQL | 16 |
| Container RAM limit | 402653184 bytes / 384 MiB |
| Container total RAM + swap limit | 536870912 bytes / 512 MiB |
| Container CPU limit | 1000000000 NanoCPUs / 1 CPU |
| `shared_buffers` | 64 MB |
| `max_connections` | 80 |
| Test transaction concurrency | At most 20 |

Recorded governor snapshots, not peak claims:

| Snapshot | RAM | Available | Commit | Swap | GPU | VRAM |
| --- | --- | --- | --- | --- | --- | --- |
| Startup readiness | 89.3% | 1734.09 MiB | 77.56% | 12.8% | 56 C | 9.83% |
| Before final strengthened RLS run | 89.9% | 1632.59 MiB | 77.95% | 13.1% | 54 C | 9.70% |

The successful runs produced no governor suspension or ceiling termination. No unrelated application was closed, and no resource limit was bypassed.

## Executed results

| Gate | Result |
| --- | --- |
| Fresh Alembic upgrade to 0004, downgrade to base, upgrade to 0004 | Passed; 3.703 seconds |
| Final full API/enterprise/worker integration suite | **53 passed; 36.19 seconds** |
| Isolated protocol/state/worker-log and request-limit regressions | **15 passed; 3.91 seconds** |
| Ruff API/enterprise/worker | All checks passed |
| Strict mypy API/enterprise/worker | No issues in **23 source files** |

An earlier run of the final integration surface exposed seven failures (43 passed). The failures were resolved as described below, then the entire 53-test suite passed. A final rerun followed the strengthened all-table read/cross-update test and is the 36.19-second result recorded above. No further database tests were repeated after that pass.

Commands executed from `apps/api`, with the repository environment installed:

```powershell
$env:RESOLVEIT_TEST_SKIP_BOOTSTRAP='1'
$env:OMP_NUM_THREADS='2'
$env:MKL_NUM_THREADS='2'
..\..\.venv\Scripts\python.exe ..\..\scripts\gpu_guard.py -- ..\..\.venv\Scripts\python.exe -m pytest -q

..\..\.venv\Scripts\python.exe -m ruff check . ..\..\enterprise ..\worker --output-format concise
$env:MYPYPATH='E:\ResolveIT App\ResolveIT\packages\resolveit-core;E:\ResolveIT App\ResolveIT\enterprise;E:\ResolveIT App\ResolveIT\apps\worker'
..\..\.venv\Scripts\python.exe -m mypy resolveit_api ..\..\enterprise\resolveit_enterprise ..\worker\resolveit_worker
```

The separate isolated-security invocation used `pytest -q -c pyproject.toml ../../tests/security/test_adversarial.py ../../tests/security/test_request_limits.py` inside the guarded Stage B final-check runner. The ignored local migration runner invoked Alembic's command API and asserted each revision plus the catalog checks below; it printed only status, counts and elapsed time, never credentials.

## Database isolation, migration and grants

The Alembic rehearsal asserted revision `0004`, then an empty version table at base, then `0004` again. It verified:

- All **20 tenant tables** have ENABLE/FORCE RLS and exactly one tenant policy.
- **13 composite foreign keys** enforce tenant-consistent incident/parent/review relationships.
- Application and migrator roles are NOSUPERUSER and NOBYPASSRLS.
- Three narrow SECURITY DEFINER functions are owned by `resolveit_auth`, use the pinned `public, pg_temp` search path, and have no PUBLIC execute grant.
- Application credentials cannot CREATE in `public`, read the Alembic metadata table, mutate API-key enrollment, rewrite/delete billing entries, advance the connector completeness watermark, mutate annotation/exposure history, change review split assignment, or change a tenant's synthetic flag. The intended timezone/status column grants remain available.

The 200-coroutine test schedules mixed tenant work behind a semaphore of 20; it does not open 200 simultaneous PostgreSQL connections. Each task reads tenant IDs across all 20 tenant tables, commits its own tenant's probe row and update, attempts a forbidden insert under a savepoint, and attempts a forbidden update against the other tenant's fixed control row.

Measured assertions: **200 legitimate inserts and updates committed; 200 cross-tenant inserts denied with SQLSTATE 42501; 200 cross-tenant updates affected zero rows; zero cross-tenant rows read; both other-tenant control values remained unchanged.** The savepoint rollback leaves the outer legitimate transaction usable. A separate regression rejects cross-tenant composite-FK references.

## Failures resolved without weakening calibration

The final synthetic bundle legitimately certifies eight destination queues at threshold 0.5: Software_Licensing, Database, Cloud_Infra, Security, ERP_Finance, HR_Systems, DevOps_CICD and Facilities_AV. Network, Identity_Access, Email_Collab and Hardware_Endpoint have no certified threshold under the fixed risk-bound policy. These queues correctly remain human-gated. Real tenants remain in shadow regardless of this generated demonstration.

Legacy API tests assumed every clear VPN ticket must route. They now exercise a genuinely certified **Database** ticket for routed intake, outbox, MCP completion and crash recovery, while a separate regression explicitly verifies unsupported Network deferral. No threshold or risk bound was changed to obtain a passing test. This is generated-fixture behavior, not a human-workload accuracy claim.

The run also found a real read-consistency defect: `load_view` chose the latest decision by wall-clock time. PostgreSQL evidence showed a final DEFER timestamp earlier than its initial ASK timestamp after a clock adjustment. The incident state was DEFERRED while its returned decision remained ASK. The query now prioritizes the semantic final stage before timestamps. A regression moves the initial timestamp one day into the future and still requires the final DEFER decision. Post-answer routing continues to fail closed because no independent answer-population certificate exists.

## Required integration regressions exercised

- **S01:** Two enrolled independent human subjects, duplicate credentials mapped to one subject, all 11 required slot labels, immutable annotations/splits, third-person adjudication, model exposure from review or REST detail blocking audit annotation, settings version conflict/tenant isolation, and honest evaluation counts. These are test identities and test labels; they do not constitute a production human-gold dataset.
- **S02:** Isolated worker failure-path regression confirms that arbitrary exception text/SQL/PII canaries are excluded; only incident ID and safe exception class are logged.
- **S03:** No verified observation watermark means no settlement. Application credentials cannot advance it. A marker one microsecond short of the full 72-hour window does not bill; exact coverage permits one eligible settlement. Repeated settlement is idempotent; bounced and synthetic incidents remain excluded.
- **S04:** Request-limit regressions cover missing/forged Content-Length, streamed oversize rejection before JSON, bounded body replay, concurrency rejection before body reads, Retry-After, capacity recovery and disconnect cleanup.
- Twelve concurrent keyed MCP calls persist one incident. Standard initialize/list/call/notification behavior, strict MRTR state verification, malformed/tampered/expired/cross-credential tokens, origin rejection and the REST citation-bypass block are covered. The official generated 2026 DiscoverResult schema regression passed; live network SDK/browser verification remains outside this stage.
- The **1,000-event Jira result is a PostgreSQL inbox/guard simulation**, including raw-byte signature checking and durable body/event deduplication. It is not a live Jira webhook, actual external delivery or an installed customer connector.
- Routed outbox persistence, injected-transport delivery, ledger chain verification, append-only grants, persist-first recovery, clarification timeout and live erasure are included in the full API suite.

## Handoff

Stage B is complete. PostgreSQL remains ready with the verified caps for Stage C. All owned verification processes exited and the heavy-job mutex is released. No UI or ML files were changed during this stage. Browser/SDK network workflows, managed-key/backup privacy, complete external connector delivery and production human calibration remain separate gates.
