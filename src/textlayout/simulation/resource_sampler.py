"""Python-based memory/CPU sampling for Palace solver invocations.

Replaces the fragile external shell sampler. A background thread polls the
live WSL memory and the resident set of the Palace worker processes while a
solve runs, so every Palace invocation can record its own peak memory without
relying on an interactive shell staying alive.

The sampler degrades gracefully: if a probe fails (WSL unavailable, transient
error) the sample is skipped rather than raising into the solver path.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import psutil  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field


def _wsl_exe() -> str | None:
    import os

    if os.name != "nt":
        return None
    return shutil.which("wsl")


def _run(script: str, *, timeout: float = 20.0) -> str:
    wsl = _wsl_exe()
    command = (
        [wsl, "-d", "Ubuntu", "--", "bash", "-lc", script]
        if wsl is not None
        else ["bash", "-lc", script]
    )
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return completed.stdout


def _parse_free_mb(free_output: str) -> dict[str, int]:
    """Parse ``free -m`` output in Python.

    awk/sed one-liners with ``$`` and single quotes are mangled by wsl.exe's
    Windows argument parsing, so the parsing is done here on the plain output.
    The ``Mem:`` row is: total used free shared buff/cache available.
    """
    for line in free_output.splitlines():
        parts = line.split()
        if parts and parts[0].rstrip(":").lower() == "mem" and len(parts) >= 7:
            nums = parts[1:7]
            if all(p.isdigit() for p in nums):
                total, used, _free, _shared, _cache, available = (int(p) for p in nums)
                return {"total_mb": total, "available_mb": available, "used_mb": used}
    return {"total_mb": 0, "available_mb": 0, "used_mb": 0}


def read_memory_budget() -> dict[str, int]:
    """Return total/available/used WSL memory in MB (best effort)."""
    return _parse_free_mb(_run("free -m"))


class ResourceBudgetDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "textlayout.palace-resource-budget.v1"
    total_ram_bytes: int = Field(ge=0)
    available_ram_bytes: int = Field(ge=0)
    configured_max_rss_bytes: int = Field(gt=0)
    maximum_allowed_rss_bytes: int = Field(gt=0)
    minimum_headroom_bytes: int = Field(ge=0)
    free_disk_bytes: int = Field(ge=0)
    estimated_field_output_bytes: int = Field(ge=0)
    estimated_mesh_output_bytes: int = Field(ge=0)
    projected_free_disk_bytes: int = Field(ge=0)
    minimum_free_disk_bytes: int = Field(ge=0)
    allowed: bool
    blockers: list[str]


def evaluate_resource_budget(
    output_dir: Path,
    *,
    configured_max_rss_bytes: int,
    estimated_field_output_bytes: int = 0,
    estimated_mesh_output_bytes: int = 0,
    maximum_rss_fraction: float = 0.70,
    minimum_headroom_fraction: float = 0.20,
    minimum_free_disk_bytes: int = 20 * 1024**3,
) -> ResourceBudgetDecision:
    memory = read_memory_budget()
    total = memory["total_mb"] * 1024**2
    available = memory["available_mb"] * 1024**2
    headroom = int(total * minimum_headroom_fraction)
    maximum = max(min(int(total * maximum_rss_fraction), available - headroom), 1)
    disk = shutil.disk_usage(output_dir.resolve().anchor or output_dir)
    projected = max(
        disk.free - estimated_field_output_bytes - estimated_mesh_output_bytes, 0
    )
    blockers: list[str] = []
    if configured_max_rss_bytes > maximum:
        blockers.append("configured RSS exceeds 70% of total WSL physical RAM")
    if available < headroom:
        blockers.append("available RAM does not preserve 20% system headroom")
    if projected < minimum_free_disk_bytes:
        blockers.append("projected free disk is below 20 GiB")
    return ResourceBudgetDecision(
        total_ram_bytes=total,
        available_ram_bytes=available,
        configured_max_rss_bytes=configured_max_rss_bytes,
        maximum_allowed_rss_bytes=maximum,
        minimum_headroom_bytes=headroom,
        free_disk_bytes=disk.free,
        estimated_field_output_bytes=estimated_field_output_bytes,
        estimated_mesh_output_bytes=estimated_mesh_output_bytes,
        projected_free_disk_bytes=projected,
        minimum_free_disk_bytes=minimum_free_disk_bytes,
        allowed=not blockers,
        blockers=blockers,
    )


class ProcessTreeResourceWatcher:
    """Enforce an RSS budget for a native process and all recursive children."""

    def __init__(
        self,
        pid: int,
        *,
        max_rss_bytes: int,
        event_path: Path,
        interval_seconds: float = 0.05,
        grace_seconds: float = 1.0,
    ) -> None:
        self.pid = pid
        self.max_rss_bytes = max_rss_bytes
        self.event_path = event_path
        self.interval_seconds = interval_seconds
        self.grace_seconds = grace_seconds

    def _atomic_event(self, payload: object) -> None:
        temporary = self.event_path.with_suffix(self.event_path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.event_path)

    def run_until_exit(self) -> dict[str, object]:
        root = psutil.Process(self.pid)
        peak = 0
        terminated = False
        while root.is_running():
            processes = [root, *root.children(recursive=True)]
            rss = sum(
                process.memory_info().rss
                for process in processes
                if process.is_running()
            )
            peak = max(peak, rss)
            if rss > self.max_rss_bytes:
                terminated = True
                self._atomic_event(
                    {
                        "schema": "textlayout.process-resource-limit-event.v1",
                        "timestamp": time.time(),
                        "root_pid": self.pid,
                        "child_pids": [process.pid for process in processes[1:]],
                        "process_group_rss_bytes": rss,
                        "max_rss_bytes": self.max_rss_bytes,
                    }
                )
                for process in reversed(processes):
                    if process.is_running():
                        process.terminate()
                _, alive = psutil.wait_procs(processes, timeout=self.grace_seconds)
                for process in alive:
                    process.kill()
                psutil.wait_procs(alive, timeout=self.grace_seconds)
                break
            time.sleep(self.interval_seconds)
        alive = root.is_running() and root.status() != psutil.STATUS_ZOMBIE
        return {
            "peak_process_group_rss_bytes": peak,
            "resource_limit_terminated": terminated,
            "orphan_process_remaining": alive,
        }


@dataclass
class ResourceSample:
    peak_used_mb: int = 0
    peak_solver_rss_mb: int = 0
    samples: int = 0
    baseline_used_mb: int = 0
    peak_solver_growth_mb: int = field(default=0)

    def to_dict(self) -> dict[str, int]:
        return {
            "peak_used_mb": self.peak_used_mb,
            "peak_solver_rss_mb": self.peak_solver_rss_mb,
            "peak_solver_growth_mb": max(self.peak_used_mb - self.baseline_used_mb, 0),
            "baseline_used_mb": self.baseline_used_mb,
            "samples": self.samples,
        }


class MemorySampler:
    """Context manager sampling peak memory while a Palace solve runs.

    Usage::

        with MemorySampler() as sampler:
            run_palace(...)
        peak = sampler.result.to_dict()
    """

    def __init__(
        self,
        *,
        interval_seconds: float = 2.0,
        process_name: str = "palace",
        solver_process_record: str | None = None,
    ) -> None:
        self.interval = interval_seconds
        self.process_name = process_name
        self.solver_process_record = solver_process_record
        self.result = ResourceSample()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _sample_once(self) -> None:
        used = _parse_free_mb(_run("free -m")).get("used_mb", 0)
        rss_kb = 0
        if self.solver_process_record:
            from pathlib import Path

            from textlayout.solvers.palace.processes import (
                inspect_owned_processes,
                refresh_solver_process_record,
            )

            record = refresh_solver_process_record(Path(self.solver_process_record))
            if record is not None:
                rss_kb = sum(
                    process.rss_kb for process in inspect_owned_processes(record)
                )
        else:
            # Compatibility fallback for direct, unmanaged invocations only.
            rss_out = _run(f"ps -o rss= -C {self.process_name}-x86_64.bin")
            rss_kb = sum(int(tok) for tok in rss_out.split() if tok.isdigit())
        rss_mb = rss_kb // 1024
        if used == 0 and rss_mb == 0:
            return
        self.result.peak_used_mb = max(self.result.peak_used_mb, used)
        self.result.peak_solver_rss_mb = max(self.result.peak_solver_rss_mb, rss_mb)
        self.result.samples += 1

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._sample_once()
            self._stop.wait(self.interval)

    def __enter__(self) -> MemorySampler:
        self.result.baseline_used_mb = read_memory_budget()["used_mb"]
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval + 5.0)
        # one final sample to catch a late peak
        self._sample_once()


def palace_reported_peak_memory_mb(text: str) -> float | None:
    """Parse Palace's own peak-memory line when present in retained stdout."""
    patterns = (
        r"(?im)^.*peak(?:\s+resident)?\s+memory\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)\s*(gb|mb|kb)",
        r"(?im)^.*maximum\s+resident\s+set\s+size\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)\s*(gb|mb|kb)",
        r"(?im)^\s*Total\s+.*?([0-9]+(?:\.[0-9]+)?)\s*([gmk])b?\s*$",
    )
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if not matches:
            continue
        value, unit = matches[-1]
        scale = {
            "g": 1024.0,
            "gb": 1024.0,
            "m": 1.0,
            "mb": 1.0,
            "k": 1.0 / 1024.0,
            "kb": 1.0 / 1024.0,
        }[unit.lower()]
        return float(value) * scale
    return None


def decide_process_count(
    requested: int, budget: dict[str, int], *, preflight_peak_mb: int | None = None
) -> dict[str, object]:
    """Documented resource gate: choose an MPI process count.

    The gate never silently changes the count; it returns the decision and the
    rationale, and the caller records it. Tiers are on peak memory as a
    fraction of available memory (using the preflight peak when known, else a
    conservative estimate scaled from the mesh is the caller's responsibility).
    """
    available = budget.get("available_mb", 0) or 1
    accepted = requested
    tier = "unknown"
    rationale = "no peak-memory estimate available; honouring the requested count"
    if preflight_peak_mb is not None:
        fraction = preflight_peak_mb / available
        if fraction < 0.60:
            tier = "low"
            accepted = requested
            rationale = f"preflight peak {preflight_peak_mb} MB < 60% of {available} MB"
        elif fraction < 0.75:
            tier = "medium"
            accepted = min(requested, 2)
            rationale = (
                f"preflight peak {preflight_peak_mb} MB is 60-75% of {available} MB; "
                "capping at 2 MPI processes"
            )
        else:
            tier = "high"
            accepted = min(requested, 2)
            rationale = (
                f"preflight peak {preflight_peak_mb} MB > 75% of {available} MB; "
                "reducing to <=2 MPI processes"
            )
    return {
        "requested_processes": requested,
        "accepted_processes": accepted,
        "memory_tier": tier,
        "rationale": rationale,
        "available_mb": budget.get("available_mb", 0),
        "total_mb": budget.get("total_mb", 0),
        "preflight_peak_mb": preflight_peak_mb,
    }
