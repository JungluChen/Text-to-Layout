"""Concrete adapters sharing the four-method external-solver lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from textlayout.models import Geometry, Technology
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation.fastercap import (
    _find_solver,
    _parse_capacitance_matrix_pf,
    prepare_idc_fastercap,
    run_fastercap,
)
from textlayout.simulation.josim import _find as find_josim
from textlayout.simulation.josim import parse_josim_csv, prepare_squid_josim, run_josim
from textlayout.simulation.models import SimulationResult
from textlayout.simulation.open_source import (
    prepare_cpw_openems,
    prepare_resonator_openems,
    prepare_spiral_fasthenry,
)
from textlayout.simulation.runners import (
    _FASTHENRY_NAMES,
    _OPENEMS_NAMES,
    extract_cpw_from_touchstone,
    extract_resonance_from_touchstone,
    find_executable,
    parse_fasthenry_inductance,
    run_fasthenry,
    run_openems,
)
from textlayout.solvers.base import SolverAdapter


@dataclass(frozen=True, slots=True)
class FasterCapAdapter:
    """IDC capacitance adapter."""

    target_capacitance_pf: float | None = None
    name: str = "FasterCap/FastCap"
    tolerance_pct: float = 10.0

    def discover(self, explicit: str | None = None) -> str | None:
        return _find_solver(explicit)

    def available(self, explicit: str | None = None) -> bool:
        return self.discover(explicit) is not None

    def prepare(
        self, spec: LayoutSpec, geometry: Geometry, technology: Technology, output_dir: str | Path
    ) -> SimulationResult:
        return prepare_idc_fastercap(spec, geometry, technology, output_dir)

    def execute(
        self,
        prepared: SimulationResult,
        *,
        executable: str | None = None,
        timeout_seconds: int = 600,
    ) -> SimulationResult:
        return run_fastercap(
            prepared,
            executable=executable,
            timeout_seconds=timeout_seconds,
            target_capacitance_pf=self.target_capacitance_pf,
            tolerance_pct=self.tolerance_pct,
        )

    def run(
        self,
        prepared: SimulationResult,
        *,
        executable: str | None = None,
        timeout_seconds: int = 600,
    ) -> SimulationResult:
        return self.execute(prepared, executable=executable, timeout_seconds=timeout_seconds)

    def parse(self, output: Path) -> list[list[float]]:
        return _parse_capacitance_matrix_pf(output.read_text(encoding="utf-8"))

    def verify(self, result: SimulationResult) -> bool:
        return result.physics_verified

    def to_evidence(self, result: SimulationResult) -> dict[str, Any]:
        return result.to_dict()


@dataclass(frozen=True, slots=True)
class OpenEMSAdapter:
    """CPW/resonator openEMS adapter."""

    component: str
    target_frequency_ghz: float | None = None
    tolerance_pct: float = 5.0
    name: str = "openEMS"

    def discover(self, explicit: str | None = None) -> str | None:
        return find_executable(_OPENEMS_NAMES, explicit, env_var="TEXTLAYOUT_OPENEMS")

    def available(self, explicit: str | None = None) -> bool:
        return self.discover(explicit) is not None

    def prepare(
        self, spec: LayoutSpec, geometry: Geometry, technology: Technology, output_dir: str | Path
    ) -> SimulationResult:
        if self.component == "CPW":
            return prepare_cpw_openems(spec, geometry, technology, output_dir)
        return prepare_resonator_openems(spec, geometry, technology, output_dir)

    def execute(
        self,
        prepared: SimulationResult,
        *,
        executable: str | None = None,
        timeout_seconds: int = 1800,
    ) -> SimulationResult:
        return run_openems(
            prepared,
            target_frequency_ghz=self.target_frequency_ghz,
            tolerance_pct=self.tolerance_pct,
            executable=executable,
            timeout_seconds=timeout_seconds,
        )

    def parse(self, output: Path) -> dict[str, float] | float:
        if self.component == "CPW":
            return extract_cpw_from_touchstone(output, self.target_frequency_ghz)
        return extract_resonance_from_touchstone(output)

    def run(
        self,
        prepared: SimulationResult,
        *,
        executable: str | None = None,
        timeout_seconds: int = 600,
    ) -> SimulationResult:
        return self.execute(prepared, executable=executable, timeout_seconds=timeout_seconds)

    def verify(self, result: SimulationResult) -> bool:
        return result.physics_verified

    def to_evidence(self, result: SimulationResult) -> dict[str, Any]:
        return result.to_dict()


@dataclass(frozen=True, slots=True)
class FastHenryAdapter:
    """Planar-inductor FastHenry adapter."""

    target_inductance_h: float | None = None
    tolerance_pct: float = 5.0
    name: str = "FastHenry"

    def discover(self, explicit: str | None = None) -> str | None:
        return find_executable(_FASTHENRY_NAMES, explicit, env_var="TEXTLAYOUT_FASTHENRY")

    def available(self, explicit: str | None = None) -> bool:
        return self.discover(explicit) is not None

    def prepare(
        self, spec: LayoutSpec, geometry: Geometry, technology: Technology, output_dir: str | Path
    ) -> SimulationResult:
        return prepare_spiral_fasthenry(spec, geometry, technology, output_dir)

    def execute(
        self,
        prepared: SimulationResult,
        *,
        executable: str | None = None,
        timeout_seconds: int = 600,
    ) -> SimulationResult:
        return run_fasthenry(
            prepared,
            target_inductance_h=self.target_inductance_h,
            tolerance_pct=self.tolerance_pct,
            executable=executable,
            timeout_seconds=timeout_seconds,
        )

    def parse(self, output: Path) -> float:
        return parse_fasthenry_inductance(output.read_text(encoding="utf-8"))

    def run(
        self,
        prepared: SimulationResult,
        *,
        executable: str | None = None,
        timeout_seconds: int = 600,
    ) -> SimulationResult:
        return self.execute(prepared, executable=executable, timeout_seconds=timeout_seconds)

    def verify(self, result: SimulationResult) -> bool:
        return result.physics_verified

    def to_evidence(self, result: SimulationResult) -> dict[str, Any]:
        return result.to_dict()


@dataclass(frozen=True, slots=True)
class JoSIMAdapter:
    """Experimental SQUID circuit adapter."""

    target_voltage_uv: float | None = None
    name: str = "JoSIM"

    def discover(self, explicit: str | None = None) -> str | None:
        return find_josim(explicit)

    def available(self, explicit: str | None = None) -> bool:
        return self.discover(explicit) is not None

    def prepare(
        self, spec: LayoutSpec, geometry: Geometry, technology: Technology, output_dir: str | Path
    ) -> SimulationResult:
        return prepare_squid_josim(spec, geometry, technology, output_dir)

    def execute(
        self,
        prepared: SimulationResult,
        *,
        executable: str | None = None,
        timeout_seconds: int = 600,
    ) -> SimulationResult:
        return run_josim(
            prepared,
            target_voltage_uv=self.target_voltage_uv,
            executable=executable,
            timeout_seconds=timeout_seconds,
        )

    def run(
        self,
        prepared: SimulationResult,
        *,
        executable: str | None = None,
        timeout_seconds: int = 600,
    ) -> SimulationResult:
        return self.execute(prepared, executable=executable, timeout_seconds=timeout_seconds)

    def parse(self, output: Path) -> dict[str, float]:
        return parse_josim_csv(output)

    def verify(self, result: SimulationResult) -> bool:
        return result.evidence_level in {
            "JOSIM_RESONANCE_CHECKED",
            "JOSIM_JJ_DYNAMICS_CHECKED",
            "JOSIM_PARAMETRIC_GAIN_CHECKED",
        }

    def to_evidence(self, result: SimulationResult) -> dict[str, Any]:
        return result.to_dict()


def adapter_for(spec: LayoutSpec) -> SolverAdapter[Any]:
    """Return the registered adapter for a supported component."""
    if spec.component == "IDC":
        return FasterCapAdapter(spec.target.get("capacitance_pf"))
    if spec.component in {"CPW", "QuarterWaveResonator"}:
        return OpenEMSAdapter(
            spec.component,
            spec.target.get("frequency_ghz"),
            10.0 if spec.component == "CPW" else 5.0,
        )
    if spec.component == "SpiralInductor":
        target = spec.target.get("inductance_h")
        if target is None and spec.target.get("inductance_nh") is not None:
            target = float(spec.target["inductance_nh"]) * 1e-9
        return FastHenryAdapter(target)
    if spec.component == "SQUID":
        return JoSIMAdapter(spec.target.get("voltage_uv"))
    raise ValueError(f"No solver adapter registered for component {spec.component!r}")
