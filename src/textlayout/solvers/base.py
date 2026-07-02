"""Common scaffolding for optional, subprocess-invoked physics solvers.

Adapters own four operations: discover, prepare, execute, and parse.  Solver
source is never vendored; this module only standardises process execution and
the retained stdout/stderr evidence used by every adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TypeVar
import subprocess
import time

from textlayout.models import Geometry, Technology
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation.models import SimulationResult

ParsedT = TypeVar("ParsedT", covariant=True)


class SolverAdapter(Protocol[ParsedT]):
    """Shape implemented by every external solver integration."""

    @property
    def name(self) -> str: ...

    def discover(self, explicit: str | None = None) -> str | None: ...

    def available(self, explicit: str | None = None) -> bool: ...

    def prepare(
        self,
        spec: LayoutSpec,
        geometry: Geometry,
        technology: Technology,
        output_dir: str | Path,
    ) -> SimulationResult: ...

    def execute(
        self,
        prepared: SimulationResult,
        *,
        executable: str | None = None,
        timeout_seconds: int = 600,
    ) -> SimulationResult: ...

    def run(
        self,
        prepared: SimulationResult,
        *,
        executable: str | None = None,
        timeout_seconds: int = 600,
    ) -> SimulationResult: ...

    def parse(self, output: Path) -> ParsedT: ...

    def verify(self, result: SimulationResult) -> bool: ...

    def to_evidence(self, result: SimulationResult) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class SolverExecution:
    """Raw subprocess outcome plus persistent solver-owned logs."""

    command: tuple[str, ...]
    returncode: int
    stdout_path: Path
    stderr_path: Path
    stdout: str
    stderr: str
    runtime_seconds: float


def run_subprocess(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: int,
    log_prefix: str = "solver",
) -> SolverExecution:
    """Run one solver command and always retain stdout/stderr on disk."""
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    stdout_path = cwd / f"{log_prefix}.stdout.txt"
    stderr_path = cwd / f"{log_prefix}.stderr.txt"
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    runtime = time.perf_counter() - started
    return SolverExecution(
        command=tuple(command),
        returncode=completed.returncode,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        stdout=completed.stdout,
        stderr=completed.stderr,
        runtime_seconds=runtime,
    )


def require_artifact(path: Path, description: str) -> Path:
    """Reject missing/empty solver outputs before they reach evidence mapping."""
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"{description} is missing or empty: {path}")
    return path


def existing_artifacts(artifacts: dict[str, str], keys: tuple[str, ...]) -> list[str]:
    """Return only non-empty files, suitable for QuantityEvidence."""
    found: list[str] = []
    for key in keys:
        value: Any = artifacts.get(key)
        if not isinstance(value, str):
            continue
        path = Path(value)
        if path.is_file() and path.stat().st_size > 0:
            found.append(value)
    return found
