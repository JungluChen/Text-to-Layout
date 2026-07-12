"""Python-based memory/CPU sampling for Palace solver invocations.

Replaces the fragile external shell sampler. A background thread polls the
live WSL memory and the resident set of the Palace worker processes while a
solve runs, so every Palace invocation can record its own peak memory without
relying on an interactive shell staying alive.

The sampler degrades gracefully: if a probe fails (WSL unavailable, transient
error) the sample is skipped rather than raising into the solver path.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
from dataclasses import dataclass, field


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

    def __init__(self, *, interval_seconds: float = 2.0, process_name: str = "palace") -> None:
        self.interval = interval_seconds
        self.process_name = process_name
        self.result = ResourceSample()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _sample_once(self) -> None:
        used = _parse_free_mb(_run("free -m")).get("used_mb", 0)
        # ``ps -o rss= -C <name>`` needs no awk/quotes: sum the RSS kB in Python.
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
