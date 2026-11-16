# ResolveIT build checkpoint

Updated: 2026-11-16 (Asia/Calcutta). Baseline: b5b8612.

## 2026-11-16 evening checkpoint (Claude continuation): INT8 bundle, serving, audit fixes

### INT8 graph: root cause and fix
- Codex's INT8 graph failed the ONNX checker (topological order inside `If` subgraphs).
  `training/toposort_graph.py` reorders losslessly; checker passes on FP32 and INT8.
- Dynamic per-tensor INT8 then failed FP32 parity: pooled cosine min 0.03, team-probability
  diff 0.999. Cause: `quantize_dynamic` also quantizes every MatMul *input activation* with one
  per-tensor scale; mDeBERTa-v3 has outlier channels. 72 of 146 MatMuls are activation x
  activation (attention). Sweep (`training/quant_sweep.py`, `artifacts/training/sweep/sweep.json`):
  QKV-only 0.75 cosine; adding FFN-up 0.05. Every per-tensor activation variant failed.
- MatMulNBits 8-bit block 32 (`training/quant_nbits.py`): accuracy level 4 cosine 0.995 but
  pooled max|diff| 2.9 and team-probability diff 0.71 (fails predeclared gate); level 0 passed
  but dequantizes every call (G2: 500 ms at 128 tokens, 311 ms pipeline on a short ticket).
- Shipped: block-32 symmetric INT8 weights for all 74 weight MatMuls, dequantized once at load,
  plus the 250k x 768 word-embedding table as INT8 rows dequantized per gathered token (file
  867 -> 315 MB; session RSS +609 MiB vs +889 MiB)
  (`training/quantize_blockwise_dq.py`, entry `training/quantize_int8.py`): cosine 0.9999,
  max|logit diff| 0.09; FP32-speed compute.

### Release-candidate bundle `968fd32c1e2b50b9dd7a5cd99ed458923137f4680454cd32c6fc5922adf5d238`
- `training/release_bundle.py`, fitted only on shipped-INT8 outputs; 10 files verified; pinned
  in `.env` as `RESOLVEIT_BUNDLE_ID`. label_source synthetic_seed; production_authorized false.
- Data: `training/data_free.py` (resolveit-freetext-v2; en/hi/hinglish clear, security, vague)
  plus Codex seed rows; disjoint splits; 0 duplicates. Rules gained Devanagari projector/meeting-room.
- Head L2 raised 1e-4 -> 5e-2 (recorded as `head_l2`): with 1e-4 / 1e-2 one of 24 policy rows
  moved 0.116 / 0.106 in team probability (> predeclared 0.10) although the encoder passed.
  Parity rows now also carry their real security flag (previously 0). Parity PASSED: team
  probability max diff 0.084; logits within 2.0 / 0.25 rmse.
- Certificates (eps 0.05, delta 0.05 Bonferroni over 12 queues): pre-answer tau 0.5 for all 12;
  post-answer certified for 10; Hardware (printer phrases inside seed templates of other teams
  dilute theta) and Security (never asks) uncertified, so those post-answer cases defer. Earlier
  all-None post-answer certificates came from the corrupted INT8 graph plus too few routed rows
  (exact binomial at delta/(12*50) needs >= ~183 zero-error routes; answer split now 320/team).
- Frozen synthetic test (624): 455 routed, 455 correct (0 misroutes); 160 ASK -> 111 answered and
  routed, all correct; 9 deferred; auto-route 90.7%; conformal coverage 0.923.
  Caveat: synthetic, template overlap; vague rows carry random labels by construction.
- G2 benchmark (4 threads): 128 tokens p50 177 / p95 197 ms; full pipeline on a short ticket
  p50 40 / p95 45 ms. Build-time (8 threads): 128 tokens p50 182 ms; typical ticket p50 42 ms.
  Target 50 ms at 128 tokens NOT met: needs a distilled student (training v2).
- Calibration pooled vectors cached per model digest under `artifacts/training/pooled_cache/`.
- Governor: Windows commit stop raised 88% -> 94% (pagefile system-managed, 16.2 GiB allocated,
  3.2 GiB used) per owner "no arbitrary ceilings, no crash"; RAM floors unchanged; 20 tests pass.

### Serving integration
- `apps/api/resolveit_api/trained_bundle.py`: requires the pinned id; verifies, then reads every
  served file into memory once (`read_verified` in core `bundle_verify.py`) and loads from those
  bytes (closes verify-then-load TOCTOU); falls back to the rule demo bundle on any failure.
  Real tenants are mapped to `shadow_bundle()` by `tenants.is_synthetic` and cannot auto-route.
- Security triggers now bypass ordinary routing (design doc requirement that was not implemented):
  DEFER with reason `security_escalation`, no question, recommended Security. Found by the live
  smoke test (`scripts/showcase_smoke.py`), which now passes on the running showcase.
- Showcase: `scripts/start_showcase.ps1` / `scripts/stop_showcase.ps1`; guide `docs/DEMO_WALKTHROUGH.md`.
  API/web run under `gpu_guard.py --shared` (ceilings watched, heavy-job slot not taken).
  Web G4 commands: typecheck, lint, 21 vitest, production build passed; browser check 0 console errors.
- Tests: API suite 61 passed against bundle 968fd32c (incl. 8 trained-bundle tests) with resolveit-audit-pg; core/scripts/
  release/training 102 passed; ruff clean; strict mypy core and API/enterprise/worker clean.

### Independent security audit (read-only agent) and remediation
- No critical/high. Fixed: M1 TOCTOU + unpinned id; M3 agent keys no longer receive decrypted
  text; L1 erasure clears the MCP body digest (sentinel keeps idempotent replay as 409);
  L2 bundle change during an open question now DEFERs with reason `bundle_changed` instead of 500;
  L5 inference and CSV analysis run off the event loop.
- Open (tracked): M2 unauthenticated slow-body slot exhaustion (gateway limits + auth-first);
  L3 CSP/HSTS and `/login` in middleware matcher (web phase); L4 server-side session revocation
  and sign-in throttling; L6 dev DB passwords in untracked `scripts/dev_native.py` (loopback only);
  I1 `/docs` exposure in production; I2 separate HKDF purpose for MCP state; I3 npm/pip audit;
  I4 security-event counters.

### Next phases (owner order)
1. Showcase boot + gates G0-G6 + live smoke. 2. Training v2: Marathi/Tamil, more data, ASR-noise
robustness, distilled student for 50 ms. 3. Voice intake (Indian-language ASR, out of the decision
path). 4. Web app redesign. 5. Full E2E (Playwright) + audit + deployment. Competitive research:
`docs/research/competitive_scan.md`.

## Latest continuation checkpoint

LatestNov16safetycheck: cleanofflineMLrerunREFUSEDbeforelaunch; available917MiB,
Windowscommit35.909/38.694GiB(2.785GiBremaining). Coordinatorrecheckphysical1111MiB,
commitfree2.76GiB. No liveownedtrainingjobs/staleResolveITprocessestoreclaim.
Dockerstopped; unrelatedUbuntu22.04WSLrunning andChrome/WebViewactive. Nonekilled.
Owneraskedtofree3-4GiBorconfirmsavedUbuntuworkbeforetargetedshutdown; awaitingreply.
Modelcheckpointfromfirstattemptpreserved;cleanrerun/export/calibrationremainpending.

2026-11-16 latestowneroverride: prioritizeactualsafetyheadroom, noarbitraryRAM/
VRAMpercentageceilings. GuardnowusesRAM750MiBhard/1024MiBsoft3poll,freeVRAM512MiB,
commit/swap88% andGPU75Cpause/78Cstop;exclusiveheavylockunchanged.19governortests
passed;ruffpassed. OneMLspecialistresumingCLEANOFFLINEpinnedcachedtraining then
export/calibration. Firstactualruncheckpointexists(2epochs576examples144micro18
updates100.97s,GPU60C,VRAM25.2%,minavailable1101MiB), butteardownhunginlibrary
safetensorsconversionthread;noexit0passclaimed. PriorownedPIDsverifieddead.
NewrunwilldisableautomaticconversionandHFnetwork/usecachedweights, captureexecuted
sourcehashatlaunch. No releasecandidatebundleorfinalG0-G6passyet.

StageEcontinuation2026-11-15: installedtorch2.9.1+cu128,transformers4.57.3,
PEFT0.18.0; actualCUDA/bf16preflightpassed. PinnedmDeBERTaSHA
a0484667b22365f84929a935b5e50a51f71f159d; tokenizerfetched; modelHTTPdownload
confirmed608174080bytesprogress (Windowsdirectorylength0wasstaleopenfilemetadata).
No actualpretrainedtraining/checkpoint/bundlepassyet. Dataset792synthetic_seed
rows/264groups, sixdisjointgroupsplits; nontrainONEpredeclaredlocale/group avoids
countingtranslationsasindependentcalibration/riskunits. Lowclasssupportexplicit.
RootfixedAPIlargeCSVadmissionseparately(maxoneCSVvs32total) afterindependent
memoryaudit;ruff+strictmypy1sourcepassed,newcancellation/capacitytestawaitsfinal
execution. APIimage/StageBreceipts predatethischange; finalG3/G5mustrerun.
G0helper+G0-G6runnerstrictmypy2sourcespassed; repositorynotcommitted/cleanyet.

2026-11-15 Phase2StageD FINALPASS: sequentialAPI/web/PgBouncerLinuximagesbuilt
exit0; guardedComposeactualdrill53.4323s passed100pooledtx(maxprepared1),tenant
settingreset,NOBYPASS,directworkerlock,restorekeynegativecontrol/externalerasure
tombstonereplay,andSAME-CODEconfigurationbluegreenrollback. Notcrossversionschema
rollback;notbackupwidekeyerasurewithoutreplay/KMS. Fivecontainers1344MiBtotalcaps
stopped/noOOM; ports8000/3000/3001/3002clear;DockerDesktopstopped. EndpointRAM
76.8->77.5%,available3758->3648MiB,commit51.33->51.49%,GPU53C,notpeaks.
See docs/audits/stage_d.md andprivateartifacts/stage-d/receipt.json.
StageEoneMLspecialistactive: noexistingtextJSONLdatasetorPyTorch/HFstackfound;
buildinghonestmultilingualsynthetic_seedtrainingdata/pinnedpretrainedpipeline.
No pretrainedtraining/exportpass yet. Gitlocalauthornowsettoownerprovidedidentity
matchinghistory;hookpathconfigured. Nocommit/finalrepo-cleanlinessclaim yet.

Phase2 StageC FINALPASS: guardedliveorchestratorexit0. OfficialMCP SDK lifecycle/
tools/list/call andstrict2026MRTRtwo-roundtripcitation+idempotentreplay passed.
Sixworkspaces at1440light/320dark:12axescanszero violations/nohorizontaloverflow.
ActualDatabaseUIroute,CSV,MCPinspector/explorer,settings,DPDPliveerasure passed;
twoAUTOMATEDsyntheticreviewercredentials savedtwo labels/statussynthetic_labeled.
Exporthuman_on_synthetic is testtenantAPI classification, notverifiedrealhuman
annotation; nohuman_gold produced. Middlewareoriginbug fixed/regression5tests;
tsc/eslint/full14pageproductionrebuild+traces passed.
FinalAPIcoldPOST239.978ms,warm30samePOSTp50203.043/p95255.621ms.
Synthetic32-inputONNXfixtureloadfirst10.324ms,warm200after200warmupp50.03045/
p95.046305ms; NOT pretrainedencoderperformance. Receipt/screenshots artifacts/stage-c;
docs/audits/stage_c.md. Cleanupports8000/3000nolisteners, nativechildrenstopped,
mutexreleased. PostRAM70.1available4838MiB commit47.295 swap1.5 GPU51 VRAM8.415.
StageDsingleops specialist active; E notstarted.

StageC resumed after owner freedmemory: guardreadyRAM64.1%, available5808.9MiB,
commit42.07%, swap2.2%, GPU52C/VRAM9.29%. Owner additionally authorized careful
RAMidentification/reclaim. CoordinatorinventoryRAM66.3%, available5465.9MiB;
no verifiedstaleResolveITprocessesfound, none terminated. Preserveactiveuserapps,
securityservices andtaskPostgresWSL. OneStageCspecialistwritingorchestrator/tests;
nativechildren notyetlaunched. Previous215MiB safetyfailure is historical only.

Phase2 StageB FINALPASS:53APItests36.19s afterstrengthened200coroutineprobe
readsall20tenanttables, denies200cross-tenantinserts and200cross-tenantupdates,
confirmsfixedcontrolrowsunchanged. RuffPASS; strictmypy23sourcesPASS;
isolatedsecurity15PASS3.91s; Alembicroundtrip3.703s. Allheavychildrenexited,
OSmutexreleased. AuditPG remainsrunning384MiB/512MiBtotalmemory+swap/CPU1,
sharedbuffers64MB/maxconnections80. Single runtime specialist assignedStageC;
D/E notstarted. StageCusesalreadybuiltNextproductionserver, noNextdev.

Phase2 StageB fullintegration PASSED53tests36.96s underheadroomgovernor/OSmutex.
Includes200boundedtenantcoroutines(20connections),200ownwrites+updates,
200deniedcrosswrites, zerocrossreads;1000inboxechoevents;12concurrentkeyedMCP;
S01exposure/independentidentity andS03watermark1microsecondboundaries.
Found/fixedfinaldecisionselection underDBclockrollback: semanticfinalstage wins
overcreated_at. Regressiontest added. Syntheticbundlecertifies8queues; Network,
Identity,Email,Hardware remainunsupportedDEFER. Routingtestsuseactuallycertified
Databasequeue; calibrationnotrelaxed. Finalstatic/securityStageBchecks pending.

Phase2 StageB intermediate evidence: guardedAlembic0004->base->0004 passed3.703s
on newlycreated disposableauditDB. Catalogverified20tenanttables ENABLE/FORCE RLS,
onepolicy each,13compositeFK,3locked-search-path authowned SECURITY DEFINER functions
withoutPUBLICexecute, app/migratorNOBYPASSRLS andprotectedledger/credential/watermark/
splitgrants. PGsettings64MBshared_buffers/80connections verified; container384MiB
RAM/512MiB totalmemory+swap/oneCPU. HostsampleRAM89.3%, available1734MiB,
commit77.56%, swap12.8%, GPU56C. Fullsuiteincluding200read/writeprobe running;
StageB not yet complete. StageC/D/E not started.

Phase2 StageA PASSED: governor18tests passed4.61s on coordinator rerun;
strictmypy1source andruffpassed. Full guarded npm run build from apps/web with
NODE_OPTIONS=--max-old-space-size=1536 exited0, compiled7.7s, generated14staticpages,
completedpageoptimization andbuildtracecollection. DockerDesktopconfirmedstopped.
Next15.5.29 webpackMemoryOptimizationstrue, oneCPU, webpackworkerdisabled,
productionBrowserSourceMapsfalse. PrebuildsamplesRAM73.9-80.1%, available3232-4235MiB,
trueWindowscommit68.71-73.26%, swap11.4-12.7%, GPU56C. Not peaktelemetry.
StageB now assigned singlebackend specialist; C/D/E notstarted. CompleteStageE
instructions received: separateNumPy12teamhead; pretrained3-outputencoder;
silver/syntheticweight0.3; sixdisjointgroupsplits; INT8onlycalibration; release
candidate manifest+latencies+G0-G6 honestscorecard. Humanproductiongate unchanged.

Phase2 owner override: stagesA->B->C->D->E strictly sequential. StageA active.
New profile: physicalRAM<=95.5%, available>=750MiB; below1024MiB softpause with
threeconsecutivepollstop; Windowscommit andswap<=88%; VRAM<=85%; GPU pause>=75C
25s, hardstop>=78C; OS-held .runtime/heavy_job.lock serializes heavy workloads.
Onlyone specialist active during governor work. Docker Desktop confirmed stopped.
Next installedconfig confirms webpackMemoryOptimizations support; enabled with
oneCPU, disabled webpackworker/browser sourcemaps. Buildheap1536MiB scheduled
after governor tests. No Phase2 runtime passes recorded yet.
StageE owner text truncated after 'With Docker stopped and GPU'; clarification
requested, pending. A-D scope complete enough to proceed independently.

Bundle-integrity stage complete: scripts/verify_bundle.py verifies actual synthetic
bundle4files against pinned SHA256 identity8be1d5cc616b46094b52e02ecf0566f1670aca7af7a4b9ede006c4c4b05b6d16.
Role6 reports12adversarialtests passed1.16s, strictmypy1source+ruffpassed.
Checks include tampering, traversal, links/junctions, duplicatekeys, changedfiles
and provenance consistency. production_authorized=false. Hash integrity does not
establish production calibration or trusted release provenance by itself.
API mypy paths now use MYPY_CONFIG_FILE_DIR; root invocation also passes23sources.

Latest continuation: full scoped Python ruff passed; strict API/enterprise/worker
mypy passed23sources from apps/api working directory; isolated security/governor
suite24passed5.45s. A coordinator mypy invocation from repository root initially
failed module resolution because existing mypy_path is cwd-relative; correct cwd
passed. Use documented apps/api cwd until configuration paths are normalized.
Measured RAM95.2% with Docker stopped: governor correctly refuses heavy jobs.
Role6 building manifest-integrity verifier and adversarial tests while runtime
remains blocked. No repeated same-configuration build retries authorized as evidence.

Final fresh continuation checks: web TypeScript+ESLint passed; Vitest20 passed
across5files after streamed-body and middleware tests. Repository Python ruff
passed across core/API/enterprise/worker/scripts/securitytests. git diff --check
passed (only Git CRLF conversion notices). Independent security10cases passed,
including official2026 discovery wire schema. ASGI ingress now caps actual streamed
bytes,10s body receive deadline and32active requests/process; BFF bodies also bounded.
Distributed gateway quotas remain release work.

Production web build retried with reduced heap and webpack worker disabled;
guard stopped compile at92.1% RAM. Docker stopped again. Migration0004 behavioral
tests, SDK live call, browserE2E/axe and full runtime are NOT passed. Next retry
requires lower baseline system RAM while preserving latest90% ceiling. No user apps
or unrelated processes were terminated to make room. Native runtime launcher added
by role6 for subsequent loopback verification; do not confuse existence with liveboot.

Owner's latest resource instruction: RAM90%, VRAM90%; GPU pause above75C and
stop78C remain. Earlier80% and intermediate95% notes below are historical only.
Six requested roles have now participated; independent security and runtime work
continue. Usage-limit interruptions preserved code; no stages assumed complete.

Fresh coordinator evidence:
- Core short tests52 passed,3 slow statistical tests deselected.
- Core strict mypy21 sources passed.
- Web TypeScript and ESLint passed after encrypted-session implementation.
- Web Vitest14 tests passed across3 files, including5 encrypted-session tests.
- Color contrast28 pairs passed in light/dark themes; this is not full WCAG audit.
- Independent security/governor tests18 passed after worker logging fix.
- Backend writer reports final ruff clean and strict mypy22 sources passed.
- Synthetic3-head opset17 INT8 smoke executed successfully7.4s; artifacts/ml-smoke
  contains model/manifest/calibration. FP32/INT8 max absolute differences:
  team0.0139584, state0.0170802, boundary0.0949447. Not pretrained text inference;
  production_eligible=false, no human performance metrics.
- Full web build compiled and generated pages but guard stopped tracephase at91%;
  production build remains unverified. Later session/auth edits require fresh build.

New source: persistent review/annotation/exposure history, settings, CSV analysis,
honest evaluation, /v1/me and Alembic0004. Post-answer certificates fail closed;
real tenants remain shadow. Security review fixed worker exception leak and requires
trusted full72h connector observation before zero-bounce settlement (disabled default).
Authenticated web sessions use AES-GCM, separate key, HttpOnly Secure __Host-cookie
in production, onehour expiry, same-origin mutations, upstream credential revalidation.
Local shared-key fallback verifies synthetic tenant. Login body streamed cap2048bytes.
Production public origin must be explicit HTTPS. These changes still need live E2E.

Current runtime blocker: starting Docker/PG raised RAM96-98%, above latest90% ceiling.
No heavy gate bypassed. Role6 reducing project resource use. Migration0004 integration,
full migration roundtrip,200coroutine RLS, officialSDK, Playwright/axe, Compose freshboot
and pretrained LoRA training remain pending. npm high PostCSS issue patched by scoped
override; remaining moderate/low CLI dependencies under review. pip-audit installed
packages reported no known vulnerabilities; local source packages skipped.

## Authorization and boundaries

Owner requests autonomous audit and full staged build. Six specialist roles run
in waves under four concurrent slots. Existing .gitignore edit preserved.
No external production deployment, Jira mutation, or secret publication performed.
No completion, calibration, or production claim without executed evidence.

## Active wave (resumed after transient agent usage limit)

- Role 1 architecture docs completed; same writer now role 4 six-workspace UI.
- Role 2 core fixes, synthetic INT8 fixture and pinned-revision LoRA entrypoint.
- Role 3 infrastructure checks completed through migration0003, now persistent workspace APIs/0004.
- Root: hardware governor, secret hook, local Compose/PgBouncer and web demo security gate.
- Isolated role5 security and role6 runtime audit still pending free agent slots.

## Confirmed findings

- Git root is ResolveIT subdirectory; six commits through b5b8612.
- No trained model; rule-weight synthetic demonstration and real-tenant shadow mode.
- Beta prior alone cannot fix ASK when shadow mode makes all post-answer route risk infinite.
- Threshold-selection multiplicity must be covered; uncorrected Wilson is insufficient.
- Concurrent MCP idempotency spans transactions; malformed signed state can crash.
- Tenant-table foreign keys need tenant-consistent composite references.
- Backup crypto-shredding promise exceeds local wrapped-key implementation.
- Live official MCP check confirms 2026-07-28 exists; compatibility issue was initialization/adapter assumptions.
- Protected error-code substrings in emails bypassed masking; ML writer repaired overlap precedence.
- Pre-answer certificates do not certify shifted post-answer probabilities; separate policy now fails closed.

## Environment

Windows PowerShell; Python 3.12.10, Node 22.15.0, uv available.
RTX 4060 Laptop: 8188 MiB, initial 55C. Heavy jobs require scripts/gpu_guard.py.
Shared .venv, ONNX/ORT, Playwright and npm dependencies installed.
PostgreSQL16 audit container ran on loopback54329; Docker stopped after DB checks to free memory.
RAM initially97.8%, later83-90%; heavy jobs blocked until <=80%. No ceilings waived.

## Evidence / remaining gates

Executed evidence (writer results, still pending isolated gatekeeper):
- API42 tests passed before final post-answer and workspace changes; stress deselected.
- 12-concurrent MCP idempotency and 1000-event in-process Jira guard included.
- Alembic0003 -> base ->0003 round-trip passed on disposable PostgreSQL16.
- API strict mypy20 sources and lint passed before workspace additions.
- Core52 short tests then34 targeted tests after gate edits; final rerun pending.
- Hardware guard9 tests passed; root scripts strict mypy4 source files passed.
- Reachable history122 blobs + local git config: zero known secret signatures after
  reviewing two loopback-template fixture false positives. Bounded signatures only.
- Compose config validated before PgBouncer addition; image boot not yet run.

Still need final core/api lint+strict types+tests, PostgreSQL16 RLS
concurrency and migrations, MCP SDK roundtrip, web build/lint/types/unit/E2E/axe,
secret/history scan, guarded ML export/calibration, runtime and latency evidence.
Human gold labels, production credentials, managed key revocation and live external
integration validation remain separate release prerequisites.

## Artifacts ready for next gates

Master audit/PRD/architecture/contracts and AGENTS on disk. Root generated private
ignored .env (values withheld), installed local .githooks/pre-commit signature scan.
No commits made: local author config absent. New docker-compose.yml includes
PostgreSQL16, setup, API through transaction PgBouncer, direct worker, Next web.
Shared-key web proxy requires RESOLVEIT_LOCAL_DEMO=true and loopback Host; origin
checks reject cross-site actions. This is a local synthetic demo, not production auth.
