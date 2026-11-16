"""Safety boundaries and cross-process heavy-job isolation."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gpu_guard
from gpu_guard import HeavyJobLock, ResourceGuard, ResourceLimit, Snapshot


@pytest.mark.parametrize(
    ("snapshot", "status"),
    [
        (Snapshot(95.5, 74, 85, 750, 88, 88), "memory_pause"),
        (Snapshot(95.51), "ready"),
        (Snapshot(90, available_mib=749.9), "stop"),
        (Snapshot(90, available_mib=1024), "ready"),
        (Snapshot(90, available_mib=1023), "memory_pause"),
        (Snapshot(80, commit_percent=94.01), "stop"),
        (Snapshot(80, commit_percent=93.0), "ready"),
        (Snapshot(80, swap_percent=88.01), "stop"),
        (Snapshot(60, 74, 99, vram_available_mib=511), "stop"),
        (Snapshot(60, 74, 93, vram_available_mib=512), "ready"),
        (Snapshot(60, 75), "cooldown"),
        (Snapshot(60, 78), "stop"),
        (Snapshot(float("nan")), "stop"),
    ],
)
def test_boundaries(snapshot: Snapshot, status: str) -> None:
    assert ResourceGuard.status(snapshot) == status


def test_soft_floor_three_polls_and_recovery() -> None:
    guard = ResourceGuard()
    low = Snapshot(94, available_mib=900)
    assert guard.poll(low) == "memory_pause"
    assert guard.poll(low) == "memory_pause"
    assert guard.poll(Snapshot(90)) == "ready"
    assert guard.soft_polls == 0
    assert [guard.poll(low) for _ in range(3)] == ["memory_pause", "memory_pause", "stop"]


def test_checkpoint_saves_before_refusing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    guard = ResourceGuard()
    guard.lock = HeavyJobLock(tmp_path / "lock")
    monkeypatch.setattr(guard, "sample", lambda: Snapshot(96, available_mib=700))
    saved: list[bool] = []
    try:
        with pytest.raises(ResourceLimit):
            guard.checkpoint(lambda: saved.append(True))
        assert saved == [True]
    finally:
        guard.close()


def test_missing_gpu_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(gpu_guard.subprocess, "run", unavailable)
    monkeypatch.setattr(gpu_guard, "windows_commit_percent", lambda: 50)
    with pytest.raises(ResourceLimit, match="GPU telemetry"):
        ResourceGuard(require_gpu=True).sample()


def test_windows_commit_pages_not_swap(monkeypatch: pytest.MonkeyPatch) -> None:
    def query(pointer: object, size: object) -> int:
        info = ctypes.cast(pointer, ctypes.POINTER(gpu_guard.PerformanceInformation)).contents
        info.CommitTotal, info.CommitLimit = 44, 100
        return 1

    function = Mock(side_effect=query)
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **kw: Mock(GetPerformanceInfo=function), raising=False)
    assert gpu_guard.windows_commit_percent() == 44
    assert function.argtypes[0] == ctypes.POINTER(gpu_guard.PerformanceInformation)


def test_windows_commit_failure_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ctypes, "WinDLL", lambda *a, **kw: Mock(GetPerformanceInfo=Mock(return_value=0)), raising=False
    )
    with pytest.raises(ResourceLimit, match="commit telemetry"):
        gpu_guard.windows_commit_percent()


def test_mutex_other_process_and_release(tmp_path: Path) -> None:
    path = tmp_path / "heavy.lock"
    code = (
        "import sys;sys.path.insert(0,sys.argv[1]);from gpu_guard import HeavyJobLock;"
        "from pathlib import Path;HeavyJobLock(Path(sys.argv[2])).acquire()"
    )
    command = [sys.executable, "-c", code, str(Path(gpu_guard.__file__).parent), str(path)]
    with HeavyJobLock(path):
        result = subprocess.run(command, capture_output=True, timeout=10)
        assert result.returncode != 0 and b"Another heavy job" in result.stderr
    result = subprocess.run(command, capture_output=True, timeout=10)
    assert result.returncode == 0
    with HeavyJobLock(path):
        assert path.is_file()


def test_inherited_owner_must_be_ancestor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESOLVEIT_HEAVY_OWNER_PID", str(os.getpid()))
    assert not gpu_guard.inherited_job()
    monkeypatch.setenv("RESOLVEIT_HEAVY_OWNER_PID", str(os.getppid()))
    assert gpu_guard.inherited_job()


def test_shared_guard_does_not_take_heavy_lock(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("RESOLVEIT_HEAVY_OWNER_PID", raising=False)
    monkeypatch.setattr(gpu_guard, "windows_commit_percent", lambda: 50)
    holder = HeavyJobLock(tmp_path / "lock")
    holder.acquire()
    guard = ResourceGuard(exclusive=False)
    guard.lock = HeavyJobLock(tmp_path / "lock")
    monkeypatch.setattr(guard, "sample", lambda: Snapshot(50))
    assert guard.checkpoint().ram_percent == 50
    holder.close()
