# Stage A safe-headroom governor

Owner override applied 2026-11-14. Owns only the launched child process tree;
unrelated applications are never selected for termination. This reduces risk but
cannot guarantee the entire OS will never freeze under unrelated workloads.

## Policy

- Physical RAM <=95.5% AND available >=750MiB; both must hold.
- Available <1024MiB triggers warning, GC, child suspension and repeat polling.
  Three consecutive low-headroom samples stop the owned child cleanly. Recovery
  to >=1024MiB resets the counter. Soft polls are spaced by the bounded interval.
- Windows GetPerformanceInfo CommitTotal/CommitLimit <=88%; no swap-percent proxy.
  Missing Windows commit telemetry fails closed. Swap usage also must be <=88%.
- VRAM <=85%; GPU temperature >=75C suspends for at least25s and rechecks while
  still suspended; >=78C stops. Require GPU telemetry for GPU training jobs.
- OS-held .runtime/heavy_job.lock excludes independent heavy jobs across processes,
  regardless of caller cwd. Kernel releases lock after owner exit/crash. Lockfile
  persists intentionally; deleting it while locked would defeat exclusion.
- Wrapper marks its PID in the child environment. Cooperative guards skip a second
  lock only when that PID is verified as an actual ancestor. Direct cooperative
  jobs acquire the lock themselves. Close guard when direct job finishes.
- Hard-limit cleanup terminates captured owned descendants, waits5s and kills only
  remaining captured descendants. Arbitrary children cannot promise a model-specific
  checkpoint; cooperating training callbacks save checkpoints before refusal.

## Fresh executed evidence

- ruff check scripts/gpu_guard.py scripts/tests/test_gpu_guard.py: passed.
- mypy --strict scripts/gpu_guard.py: passed1source.
- pytest scripts/tests/test_gpu_guard.py -q -p no:asyncio:18passed3.15s.
- Tests cover exact physical/commit/swap/VRAM/thermal boundaries, invalid telemetry,
  three-poll hysteresis/reset, checkpoint-before-refusal, Windows commit page ratio,
  telemetry failure, actual second-process exclusion/release and ancestor checking.
- Real Windows sample: RAM73.9%,available4235.11MiB,commit68.71%,swap11.4%,
  GPU56C,VRAM11.47%. Guardready. Earlier sample80.1%RAM/73.26%commit also ready.

No build/runtime pass inferred from governor tests. Parent coordinator owns Next
build, AGENTS/checkpoint updates and subsequent sequential stages.
