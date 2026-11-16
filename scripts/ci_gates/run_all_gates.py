"""Sequential, fail-closed release checks with redacted execution receipts.

Use --plan while another heavy job owns the governor. Actual execution acquires
the repository heavy-job mutex. G6 tests configuration rollback only; it never
certifies cross-version database rollback or production human calibration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

GATES = tuple(f"G{i}" for i in range(7))
PY = sys.executable
NPM = shutil.which("npm.cmd" if os.name == "nt" else "npm") or "npm"
NPX = shutil.which("npx.cmd" if os.name == "nt" else "npx") or "npx"


def plan(gate: str, bundle: Path, output: Path, expected_id: str | None) -> list[tuple[list[str], Path]]:
    web = ROOT / "apps/web"
    if gate == "G0":
        return [
            ([PY, "scripts/ci_gates/g0_repo.py"], ROOT),
            ([PY, "scripts/secret_scan.py", "--history"], ROOT),
            ([PY, "scripts/secret_scan.py", "--staged"], ROOT),
        ]
    if gate == "G1":
        return [
            (
                [
                    PY,
                    "-m",
                    "ruff",
                    "check",
                    "packages/resolveit-core",
                    "apps/api",
                    "enterprise",
                    "apps/worker",
                    "scripts",
                    "training",
                    "tests",
                ],
                ROOT,
            ),
            (
                [
                    PY,
                    "-m",
                    "mypy",
                    "--strict",
                    "--config-file",
                    "packages/resolveit-core/pyproject.toml",
                    "packages/resolveit-core/resolveit_core",
                ],
                ROOT,
            ),
            (
                [
                    PY,
                    "-m",
                    "mypy",
                    "--config-file",
                    "apps/api/pyproject.toml",
                    "apps/api/resolveit_api",
                    "enterprise/resolveit_enterprise",
                    "apps/worker/resolveit_worker",
                ],
                ROOT,
            ),
            (
                [
                    PY,
                    "-m",
                    "pytest",
                    "packages/resolveit-core/tests",
                    "scripts/tests",
                    "tests/release",
                    "tests/training",
                    "-q",
                ],
                ROOT,
            ),
        ]
    if gate == "G2":
        verify = [PY, "scripts/verify_bundle.py", str(bundle)]
        if expected_id:
            verify += ["--expected-id", expected_id]
        return [
            (verify, ROOT),
            (
                [
                    PY,
                    "training/benchmark_bundle.py",
                    "--bundle",
                    str(bundle),
                    "--output",
                    str(output / "pretrained-benchmark.json"),
                    *(["--expected-id", expected_id] if expected_id else []),
                ],
                ROOT,
            ),
        ]
    if gate == "G3":
        return [([PY, "scripts/ci_gates/stage_b.py"], ROOT)]
    if gate == "G4":
        return [
            ([NPM, "run", "typecheck"], web),
            ([NPM, "run", "lint"], web),
            ([NPX, "vitest", "run", "--maxWorkers=1"], web),
            ([NPM, "run", "build"], web),
            ([PY, "scripts/runtime_stage_c.py"], ROOT),
        ]
    if gate == "G5":
        return [
            (["docker", "compose", "build", service], ROOT) for service in ("api", "web", "pgbouncer")
        ] + [([PY, "scripts/runtime_stage_d.py"], ROOT)]
    return []


def source_hash() -> str:
    paths = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    digest = hashlib.sha256()
    for name in sorted(set(paths.decode("utf-8").split("\0"))):
        path = ROOT / name
        if name and path.is_file():
            digest.update(name.encode("utf-8") + b"\0")
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(65536), b""):
                    digest.update(chunk)
    return digest.hexdigest()


def execute(command: list[str], cwd: Path, env: dict[str, str]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=7200)
        # Raw diagnostics may contain SQL values or credentials. Persist only
        # byte counts and hashes, never arbitrary stdout/stderr bodies.
        return {
            "command": command,
            "cwd": str(cwd),
            "exit_code": result.returncode,
            "seconds": time.perf_counter() - started,
            "stdout_bytes": len(result.stdout),
            "stderr_bytes": len(result.stderr),
            "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "command": command,
            "cwd": str(cwd),
            "exit_code": None,
            "seconds": time.perf_counter() - started,
            "error_class": type(exc).__name__,
        }


KEEP_ENGINE = False


def engine(action: str, env: dict[str, str]) -> dict[str, Any]:
    # --keep-engine: leave Docker Desktop running between gates. On some Windows hosts a
    # stop leaves stale AF_UNIX socket files under %LOCALAPPDATA%/Docker/run that block the
    # next start; keeping the engine up avoids that at the cost of ~2 GiB resident memory.
    if KEEP_ENGINE:
        return {"command": ["docker", "desktop", action], "exit_code": 0, "skipped": "keep-engine"}
    return execute(["docker", "desktop", action], ROOT, env)


def main() -> int:
    from scripts.gpu_guard import inherited_job

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", action="append", choices=GATES)
    parser.add_argument("--bundle", type=Path, default=ROOT / "artifacts/release_candidate_bundle")
    parser.add_argument("--expected-id", help="Trusted release-channel bundle identity; required for G2")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/release-gates")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--keep-engine", action="store_true", help="do not stop/start Docker Desktop")
    args = parser.parse_args()
    selected = [gate for gate in GATES if gate in (args.gate or GATES)]
    global KEEP_ENGINE
    KEEP_ENGINE = args.keep_engine
    if args.plan:
        print(
            json.dumps(
                {
                    gate: [cmd for cmd, _ in plan(gate, args.bundle, args.output, args.expected_id)]
                    for gate in selected
                },
                indent=2,
            )
        )
        return 0
    if not inherited_job():
        return subprocess.call(
            [PY, str(ROOT / "scripts/gpu_guard.py"), "--", PY, str(Path(__file__)), *sys.argv[1:]], cwd=ROOT
        )
    args.output.mkdir(parents=True, exist_ok=True)
    env = dict(
        os.environ,
        OMP_NUM_THREADS="2",
        OPENBLAS_NUM_THREADS="2",
        MKL_NUM_THREADS="2",
        NODE_OPTIONS="--max-old-space-size=1536",
        NEXT_TELEMETRY_DISABLED="1",
        RESOLVEIT_TEST_SKIP_BOOTSTRAP="1",
    )
    receipt: dict[str, Any] = {
        "started_utc": datetime.now(UTC).isoformat(),
        "source_sha256": source_hash(),
        "gates": {},
        "production_authorized": False,
    }
    runtime_passed = False
    engine_started = False
    try:
        for gate in selected:
            checks: list[dict[str, Any]] = []
            if gate in {"G1", "G2"}:
                checks.append(engine("stop", env))
            if gate in {"G3", "G5"}:
                checks.append(engine("start", env))
                engine_started = True
            if gate == "G3":
                checks.append(execute(["docker", "start", "resolveit-audit-pg"], ROOT, env))
            if gate == "G5":
                checks.append(execute(["docker", "stop", "resolveit-audit-pg"], ROOT, env))
            if any(check["exit_code"] != 0 for check in checks):
                checks.append({"exit_code": None, "error_class": "PrerequisiteCommandFailed"})
            elif gate == "G2" and not args.expected_id:
                checks.append({"exit_code": None, "error_class": "MissingTrustedBundleIdentity"})
            elif gate == "G6":
                stage_d = ROOT / "artifacts/stage-d/receipt.json"
                data = json.loads(stage_d.read_text()) if runtime_passed and stage_d.is_file() else {}
                configuration = data.get("blue_green", {})
                valid = bool(
                    data.get("passed")
                    and configuration.get("rollback_recovered")
                    and configuration.get("cutover_smoke_failure")
                    and data.get("backup_restore_erasure", {}).get("external_tombstone_replay_passed")
                )
                checks.append(
                    {
                        "exit_code": 0 if valid else 1,
                        "fresh_same_run_stage_d": runtime_passed,
                        "scope": "same-code configuration rollback; not cross-version schema rollback",
                    }
                )
            else:
                for command, cwd in plan(gate, args.bundle, args.output, args.expected_id):
                    if gate == "G4" and command[:3] == [NPM, "run", "build"]:
                        checks.append(engine("stop", env))
                    if gate == "G4" and command[-1] == "scripts/runtime_stage_c.py":
                        checks.append(engine("start", env))
                        engine_started = True
                        checks.append(execute(["docker", "start", "resolveit-audit-pg"], ROOT, env))
                    check = execute(command, cwd, env)
                    checks.append(check)
                    if check["exit_code"] != 0:
                        break
            passed = bool(checks) and all(check["exit_code"] == 0 for check in checks)
            if gate == "G5":
                runtime_passed = passed
            receipt["gates"][gate] = {"status": "passed" if passed else "failed", "checks": checks}
            (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
            print(f"{gate}: {'passed' if passed else 'failed'}; redacted receipt saved", flush=True)
    finally:
        receipt["cleanup"] = (
            [execute(["docker", "compose", "stop"], ROOT, env), engine("stop", env)] if engine_started else []
        )
        receipt["finished_utc"] = datetime.now(UTC).isoformat()
        receipt["passed"] = (
            all(item["status"] == "passed" for item in receipt["gates"].values())
            and len(receipt["gates"]) == len(selected)
            and all(item["exit_code"] == 0 for item in receipt["cleanup"])
        )
        (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
