"""Common lifecycle for circuit-level superconducting simulators.

JoSIM, PSCAN2, and WRspice all speak through this one interface:
``available → version → prepare → run → parse → postprocess → to_evidence``.

Scope guard (the project's core boundary): these simulators validate
*circuit-level* transient behaviour from already-known L/C/JJ parameters.
They are never accepted as proof that a physical IDC geometry has its target
capacitance — that is FasterCap/FastCap territory.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

from textlayout.simulation.evidence import circuit_evidence
from textlayout.simulation.models import SimulationResult, target_comparison
from textlayout.simulation.postprocess import (
    Waveform,
    estimate_resonance_ghz,
    parse_waveform_table,
)
from textlayout.simulation.templates import LCResonanceCheck


def tools_root() -> Path:
    """The local third-party tool directory (git-ignored, never under src/).

    ``TEXTLAYOUT_TOOLS_DIR`` overrides; the default is ``<repo>/.tools`` for
    the editable-install layout this project ships with. This mirrors
    ``scripts/check_simulators.py`` so runtime detection and the checker can
    never disagree.
    """
    override = os.environ.get("TEXTLAYOUT_TOOLS_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / ".tools"


def find_simulator(
    env_var: str,
    executable_names: tuple[str, ...],
    explicit: str | None = None,
    *,
    tool_subdir: str | None = None,
) -> str | None:
    """Resolve a simulator executable.

    Priority (identical to ``scripts/check_simulators.py``): explicit arg →
    env var → ``.tools/<tool_subdir>/bin/<name>`` → PATH names.
    """
    candidate = explicit or os.environ.get(env_var)
    if candidate:
        path = Path(candidate)
        if path.is_file():
            return str(path)
        return shutil.which(candidate)
    if tool_subdir is not None:
        bin_dir = tools_root() / tool_subdir / "bin"
        for name in executable_names:
            tool_path = bin_dir / name
            if tool_path.is_file():
                return str(tool_path)
    return next((found for name in executable_names if (found := shutil.which(name))), None)


def capture_version(executable: str, cwd: Path | None = None) -> str | None:
    """Best-effort one-line version/help banner from a solver executable."""
    for flag in ("--version", "-v", "--help", "-h"):
        try:
            result = subprocess.run(
                [executable, flag],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        text = (result.stdout or result.stderr).strip()
        if text:
            return text.splitlines()[0][:200]
    return None


class CircuitSimulatorAdapter(ABC):
    """One superconducting circuit simulator behind the shared lifecycle."""

    name: ClassVar[str]
    env_var: ClassVar[str]
    executable_names: ClassVar[tuple[str, ...]]
    #: Subdirectory of the git-ignored ``.tools/`` directory holding a local
    #: install (checked between the env var and PATH), or ``None``.
    tool_subdir: ClassVar[str | None] = None

    def discover(self, explicit: str | None = None) -> str | None:
        return find_simulator(
            self.env_var, self.executable_names, explicit, tool_subdir=self.tool_subdir
        )

    def available(self, explicit: str | None = None) -> bool:
        return self.discover(explicit) is not None

    def version(self, explicit: str | None = None) -> str | None:
        executable = self.discover(explicit)
        return capture_version(executable) if executable is not None else None

    @abstractmethod
    def prepare(self, template: LCResonanceCheck, output_dir: str | Path) -> SimulationResult:
        """Write the simulator's own input files; never execute anything."""

    @abstractmethod
    def run(
        self,
        prepared: SimulationResult,
        *,
        executable: str | None = None,
        timeout_seconds: int = 600,
    ) -> SimulationResult:
        """Execute if available; otherwise return an honest skipped record."""

    def parse(self, output: str | Path) -> Waveform:
        """Parse raw simulator output into the uniform waveform shape."""
        return parse_waveform_table(output)

    def postprocess(
        self,
        waveform: Waveform,
        *,
        analytical_resonance_ghz: float | None = None,
        tolerance_percent: float = 10.0,
    ) -> dict[str, Any]:
        """Shared LC metrics: sample count, columns, resonance vs analytical."""
        metrics: dict[str, Any] = {
            "sample_count": len(waveform["time_s"]),
            "signal_names": list(waveform["signals"]),
        }
        voltage = next(iter(waveform["signals"].values()), [])
        measured = estimate_resonance_ghz(waveform["time_s"], voltage)
        if measured is not None:
            metrics["resonance_ghz"] = measured
            if analytical_resonance_ghz is not None:
                metrics["target_comparison"] = target_comparison(
                    measured, analytical_resonance_ghz, tolerance_percent, "resonance_ghz"
                )
        return metrics

    def to_evidence(self, result: SimulationResult) -> dict[str, Any]:
        executable = self.discover()
        return circuit_evidence(
            result,
            simulator=self.name,
            executable=executable,
            version=result.solver_version,
        )
