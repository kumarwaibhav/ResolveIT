"""16 GiB safe-headroom governor. Only the owned child process tree is managed."""

from __future__ import annotations

import argparse
import contextlib
import csv
import ctypes
import gc
import io
import math
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, BinaryIO

import psutil

ROOT = Path(__file__).resolve().parents[1]


class ResourceLimit(RuntimeError):
    """Checkpoint and stop; no permission to affect unrelated applications."""


class PerformanceInformation(ctypes.Structure):
    _fields_ = (
        [("cb", ctypes.c_ulong)]
        + [
            (name, ctypes.c_size_t)
            for name in (
                "CommitTotal",
                "CommitLimit",
                "CommitPeak",
                "PhysicalTotal",
                "PhysicalAvailable",
                "SystemCache",
                "KernelTotal",
                "KernelPaged",
                "KernelNonpaged",
                "PageSize",
            )
        ]
        + [(name, ctypes.c_ulong) for name in ("HandleCount", "ProcessCount", "ThreadCount")]
    )


def windows_commit_percent() -> float:
    """GetPerformanceInfo reports total committed pages / commit-limit pages."""
    info = PerformanceInformation()
    info.cb = ctypes.sizeof(info)
    try:
        library = ctypes.WinDLL("psapi", use_last_error=True)
        function = library.GetPerformanceInfo
        function.argtypes = [ctypes.POINTER(PerformanceInformation), ctypes.c_ulong]
        function.restype = ctypes.c_int
        if not function(ctypes.byref(info), info.cb) or info.CommitLimit == 0:
            raise ResourceLimit("Windows commit telemetry unavailable")
        return float(100.0 * info.CommitTotal / info.CommitLimit)
    except (AttributeError, OSError) as exc:
        raise ResourceLimit("Windows commit telemetry unavailable") from exc


@dataclass(frozen=True)
class Snapshot:
    ram_percent: float
    gpu_temperature: float | None = None
    vram_percent: float | None = None
    available_mib: float = 2048
    commit_percent: float | None = None
    swap_percent: float = 0
    vram_available_mib: float | None = None


class HeavyJobLock:
    """OS-held byte/file lock: process exit releases ownership; file never unlinked."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or ROOT / ".runtime/heavy_job.lock"
        self.file: BinaryIO | None = None

    def acquire(self) -> None:
        if self.file is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl: Any = __import__("fcntl")
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise ResourceLimit("Another heavy job owns .runtime/heavy_job.lock") from exc
        self.file = handle

    def close(self) -> None:
        if self.file is not None:
            self.file.close()
            self.file = None

    def __enter__(self) -> HeavyJobLock:
        self.acquire()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def inherited_job() -> bool:
    value = os.environ.get("RESOLVEIT_HEAVY_OWNER_PID", "")
    if not value.isdecimal():
        return False
    try:
        return int(value) in {p.pid for p in psutil.Process().parents()}
    except psutil.Error:
        return False


class ResourceGuard:
    RAM_LIMIT_PERCENT = 95.5
    VRAM_LIMIT_PERCENT = 85.0

    def __init__(
        self, *, require_gpu: bool = False, cooldown_seconds: float = 25, exclusive: bool = True
    ) -> None:
        self.require_gpu = require_gpu
        # exclusive=False: long-lived servers (showcase API/web) are watched for ceilings but do
        # not take the single heavy-job slot, so API and web can run side by side.
        self.exclusive = exclusive
        self.cooldown_seconds = max(25, cooldown_seconds)
        self.soft_polls = 0
        self.lock = HeavyJobLock()

    def close(self) -> None:
        self.lock.close()

    def sample(self) -> Snapshot:
        memory, swap = psutil.virtual_memory(), psutil.swap_memory()
        commit = windows_commit_percent() if os.name == "nt" else None
        readings: list[tuple[float, float, float]] = []
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=temperature.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            readings = [
                (float(r[0]), 100 * float(r[1]) / float(r[2]), float(r[2]) - float(r[1]))
                for r in csv.reader(io.StringIO(result.stdout))
            ]
            if not readings or any(not all(math.isfinite(v) for v in r) for r in readings):
                raise ValueError("Invalid GPU telemetry")
        except (OSError, ValueError, ZeroDivisionError, subprocess.SubprocessError):
            if self.require_gpu:
                raise ResourceLimit("GPU telemetry unavailable") from None
        return Snapshot(
            float(memory.percent),
            max((r[0] for r in readings), default=None),
            max((r[1] for r in readings), default=None),
            memory.available / 2**20,
            commit,
            float(swap.percent),
            min((r[2] for r in readings), default=None),
        )

    @staticmethod
    def status(s: Snapshot) -> str:
        values = [s.ram_percent, s.available_mib, s.swap_percent]
        values.extend(
            v
            for v in (s.commit_percent, s.gpu_temperature, s.vram_percent, s.vram_available_mib)
            if v is not None
        )
        if not all(math.isfinite(v) and v >= 0 for v in values):
            return "stop"
        if (
            s.available_mib < 750
            or s.swap_percent > 88
            # Owner override 2026-11-16: no arbitrary ceilings, only no crash. The pagefile is
            # system-managed (it grows), so commit stops at 94%; real RAM floors stay.
            or (s.commit_percent is not None and s.commit_percent > 94)
            or (s.vram_available_mib is not None and s.vram_available_mib < 512)
            or (s.gpu_temperature is not None and s.gpu_temperature >= 78)
        ):
            return "stop"
        if s.gpu_temperature is not None and s.gpu_temperature >= 75:
            return "cooldown"
        if s.available_mib < 1024:
            return "memory_pause"
        return "ready"

    def poll(self, snapshot: Snapshot) -> str:
        status = self.status(snapshot)
        self.soft_polls = self.soft_polls + 1 if snapshot.available_mib < 1024 else 0
        if self.soft_polls >= 3:
            return "stop"
        return status

    def checkpoint(self, save: Callable[[], Any] | None = None) -> Snapshot:
        if self.exclusive and not inherited_job():
            self.lock.acquire()
        while True:
            snapshot = self.sample()
            status = self.poll(snapshot)
            if status == "ready":
                return snapshot
            if save is not None:
                save()
            if status == "stop":
                raise ResourceLimit(f"Resource ceiling reached: {asdict(snapshot)}")
            if status == "memory_pause":
                print("Low physical headroom: GC/pause before next safety poll", file=sys.stderr)
            gc.collect()
            time.sleep(self.cooldown_seconds if status == "cooldown" else 2)


def stop_tree(child: subprocess.Popen[bytes]) -> None:
    """Terminate only descendants captured from our child, then kill stragglers."""
    with contextlib.suppress(psutil.NoSuchProcess):
        processes = psutil.Process(child.pid).children(recursive=True)
        processes.append(psutil.Process(child.pid))
        for process in processes:
            with contextlib.suppress(psutil.NoSuchProcess):
                process.resume()
                process.terminate()
        _, alive = psutil.wait_procs(processes, timeout=5)
        for process in alive:
            with contextlib.suppress(psutil.NoSuchProcess):
                process.kill()
    with contextlib.suppress(subprocess.TimeoutExpired):
        child.wait(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-gpu", action="store_true")
    parser.add_argument("--interval", type=float, default=2)
    parser.add_argument("--shared", action="store_true", help="watch ceilings without the heavy-job lock")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not math.isfinite(args.interval) or not 0.1 <= args.interval <= 5:
        parser.error("interval must be finite and between0.1 and5seconds")
    guard = ResourceGuard(require_gpu=args.require_gpu, exclusive=not args.shared)
    child: subprocess.Popen[bytes] | None = None
    try:
        snapshot = guard.checkpoint()
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        if not command:
            print(asdict(snapshot))
            return 0
        env = dict(os.environ, RESOLVEIT_HEAVY_OWNER_PID=str(os.getpid()))
        child = subprocess.Popen(command, env=env)
        while child.poll() is None:
            sample = guard.sample()
            status = guard.poll(sample)
            if status == "stop":
                raise ResourceLimit(f"Child stopped at ceiling: {asdict(sample)}")
            if status != "ready":
                if status == "memory_pause":
                    print("Low physical headroom: suspending owned child tree", file=sys.stderr)
                processes = psutil.Process(child.pid).children(recursive=True)
                processes.append(psutil.Process(child.pid))
                for process in processes:
                    with contextlib.suppress(psutil.NoSuchProcess):
                        process.suspend()
                try:
                    while status != "ready":
                        gc.collect()
                        time.sleep(guard.cooldown_seconds if status == "cooldown" else args.interval)
                        sample = guard.sample()
                        status = guard.poll(sample)
                        if status == "stop":
                            raise ResourceLimit(f"Child stopped at ceiling: {asdict(sample)}")
                finally:
                    for process in processes:
                        with contextlib.suppress(psutil.NoSuchProcess):
                            process.resume()
            else:
                time.sleep(args.interval)
        return int(child.returncode or 0)
    except (ResourceLimit, KeyboardInterrupt) as exc:
        print(str(exc), file=sys.stderr)
        return 75
    finally:
        if child is not None and child.poll() is None:
            stop_tree(child)
        guard.close()


if __name__ == "__main__":
    raise SystemExit(main())
