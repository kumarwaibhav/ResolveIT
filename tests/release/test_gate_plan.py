"""Gate planning must not silently certify missing execution or leak diagnostics."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/ci_gates/{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_full_core_plan_keeps_statistical_tests_and_no_slow_exclusion(tmp_path: Path) -> None:
    gate = load("run_all_gates")
    commands = [cmd for cmd, _ in gate.plan("G1", tmp_path, tmp_path, None)]
    assert any("packages/resolveit-core/tests" in cmd and "pytest" in cmd for cmd in commands)
    assert all("not slow" not in " ".join(cmd) for cmd in commands)


def test_model_gate_requires_trusted_identity_and_real_bundle_benchmark(tmp_path: Path) -> None:
    gate = load("run_all_gates")
    commands = [cmd for cmd, _ in gate.plan("G2", tmp_path / "model", tmp_path, "a" * 64)]
    assert commands[0][-2:] == ["--expected-id", "a" * 64]
    assert commands[1][1] == "training/benchmark_bundle.py"
    assert "ml_smoke.py" not in " ".join(part for command in commands for part in command)


def test_image_builds_are_individual_and_ordered(tmp_path: Path) -> None:
    gate = load("run_all_gates")
    commands = [cmd for cmd, _ in gate.plan("G5", tmp_path, tmp_path, None)]
    assert [cmd[-1] for cmd in commands[:3]] == ["api", "web", "pgbouncer"]
    assert all(cmd[:3] == ["docker", "compose", "build"] for cmd in commands[:3])


def test_no_cached_receipt_can_satisfy_g6_plan(tmp_path: Path) -> None:
    gate = load("run_all_gates")
    assert gate.plan("G6", tmp_path, tmp_path, None) == []
    # Execution authorizes G6 only after G5 in the same invocation.
    assert "fresh_same_run_stage_d" in (ROOT / "scripts/ci_gates/run_all_gates.py").read_text()


def test_command_receipt_never_persists_raw_secret_output(monkeypatch: pytest.MonkeyPatch) -> None:
    gate = load("run_all_gates")
    monkeypatch.setattr(
        gate.subprocess,
        "run",
        Mock(
            return_value=Mock(
                returncode=1, stdout=b"planted-secret-and-ticket", stderr=b"Authorization: planted-token"
            )
        ),
    )
    receipt = gate.execute(["fake"], ROOT, {})
    encoded = json.dumps(receipt)
    assert receipt["exit_code"] == 1
    assert "planted" not in encoded and "Authorization" not in encoded
    assert receipt["stdout_bytes"] > 0 and len(receipt["stderr_sha256"]) == 64


def test_stage_b_rejects_unowned_container(monkeypatch: pytest.MonkeyPatch) -> None:
    gate = load("stage_b")
    monkeypatch.setattr(
        gate,
        "run",
        lambda *a, **kw: json.dumps([{"Config": {"Labels": {}}, "State": {"Running": True}}]).encode(),
    )
    with pytest.raises(RuntimeError, match="task-owned"):
        gate.verify_container()


@pytest.mark.parametrize(
    "source",
    [
        "import resolveit_enterprise.privacy\n",
        "from enterprise import privacy\n",
        "__import__('resolveit_enterprise.privacy')\n",
        "importlib.import_module(name='enterprise.privacy')\n",
    ],
)
def test_core_boundary_rejects_static_and_literal_dynamic_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    gate = load("g0_repo")
    name = "packages/resolveit-core/resolveit_core/probe.py"
    target = tmp_path / name
    target.parent.mkdir(parents=True)
    target.write_text(source)
    (tmp_path / "packages/resolveit-core/LICENSE").write_text("Apache License Version 2.0")
    hook = tmp_path / ".githooks/pre-commit"
    hook.parent.mkdir()
    hook.write_text("#!/bin/sh\n")
    monkeypatch.setattr(gate, "ROOT", tmp_path)

    def fake_git(*args: str) -> str:
        if args[0] == "ls-files":
            return name + "\0"
        if args[:3] == ("config", "--local", "user.name"):
            return "Kumar Waibhav Akshat"
        if args[:3] == ("config", "--local", "user.email"):
            return "kwa.waibhav@gmail.com"
        if args[:3] == ("config", "--local", "core.hooksPath"):
            return ".githooks"
        return ""

    monkeypatch.setattr(gate, "git", fake_git)
    receipt = gate.audit()
    assert not receipt["passed"]
    assert any("enterprise import" in issue for issue in receipt["errors"])
