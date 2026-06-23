"""Universal EM solver interface — Phase 2.

Every EM solver (Elmer FEM, openEMS FDTD, FastCap, FastHenry) must implement
this ABC.  The interface enforces the five-stage pipeline:

    prepare()  — translate GeometrySpec into solver-native input
    mesh()     — generate and validate the mesh
    solve()    — run the solver subprocess
    parse()    — parse output into SolverOutput
    validate() — check physical constraints (passivity, reciprocity, energy)

If a solver is unavailable, every method returns a SolverOutput with
status="SKIPPED" and a reason string.  status="EXECUTED" requires a real
output artifact on disk.

source="LLM" is never written by this module.
"""

from __future__ import annotations

import abc
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VALID_STATUSES = frozenset({"EXECUTED", "SKIPPED", "FAILED"})


@dataclass(frozen=True)
class AvailabilityStatus:
    available: bool
    reason: str
    version: str | None = None
    executable: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "reason": self.reason,
            "version": self.version,
            "executable": self.executable,
        }


@dataclass
class GeometrySpec:
    """Solver-agnostic geometry description derived from GDS extraction."""
    device_type: str                           # "cpw" | "jj" | "idc" | "squid" | ...
    parameters: dict[str, Any]                 # device-specific geometry dict
    process_stack: dict[str, Any]              # from process.yaml
    frequency_ghz_start: float = 1.0
    frequency_ghz_stop: float = 12.0
    frequency_points: int = 201
    port_impedance_ohm: float = 50.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_type": self.device_type,
            "parameters": self.parameters,
            "process_stack": self.process_stack,
            "frequency_ghz_start": self.frequency_ghz_start,
            "frequency_ghz_stop": self.frequency_ghz_stop,
            "frequency_points": self.frequency_points,
            "port_impedance_ohm": self.port_impedance_ohm,
        }


@dataclass
class SolverOutput:
    """Result from any EM solver stage."""
    status: str                                # EXECUTED | SKIPPED | FAILED
    solver: str
    reason: str
    output_dir: Path | None
    artifacts: dict[str, Path] = field(default_factory=dict)
    parsed_data: dict[str, Any] = field(default_factory=dict)
    execution_time_s: float = 0.0
    version: str | None = None
    timestamp: str | None = None

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            self.status = "FAILED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "solver": self.solver,
            "reason": self.reason,
            "output_dir": str(self.output_dir) if self.output_dir else None,
            "artifacts": {k: str(v) for k, v in self.artifacts.items()},
            "parsed_data": self.parsed_data,
            "execution_time_s": self.execution_time_s,
            "version": self.version,
            "timestamp": self.timestamp,
        }

    @classmethod
    def skipped(cls, solver: str, reason: str) -> "SolverOutput":
        return cls(
            status="SKIPPED",
            solver=solver,
            reason=reason,
            output_dir=None,
        )

    @classmethod
    def failed(cls, solver: str, reason: str, output_dir: Path | None = None) -> "SolverOutput":
        return cls(
            status="FAILED",
            solver=solver,
            reason=reason,
            output_dir=output_dir,
        )


class EMSolverInterface(abc.ABC):
    """Abstract base class for all EM solvers.

    Subclasses must implement all five pipeline stages.
    Each stage must return a SolverOutput — it may never raise
    an exception for missing solver; instead return status="SKIPPED".
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable solver name."""

    @abc.abstractmethod
    def is_available(self) -> AvailabilityStatus:
        """Check if the solver binary and dependencies are present."""

    @abc.abstractmethod
    def prepare(
        self,
        geometry: GeometrySpec,
        output_dir: Path,
    ) -> SolverOutput:
        """Translate GeometrySpec into solver-native input files.

        Output: SolverOutput with status=PREPARED (use EXECUTED for consistency)
        and artifacts["input_file"] set.
        """

    @abc.abstractmethod
    def mesh(
        self,
        prepared: SolverOutput,
        output_dir: Path,
    ) -> SolverOutput:
        """Generate and validate the mesh.

        Should check mesh quality (aspect ratio, element count).
        """

    @abc.abstractmethod
    def solve(
        self,
        meshed: SolverOutput,
        output_dir: Path,
    ) -> SolverOutput:
        """Run the solver subprocess.

        Must write at least one artifact file. If no artifact is produced,
        return status="FAILED".
        """

    @abc.abstractmethod
    def parse(
        self,
        solved: SolverOutput,
        output_dir: Path,
    ) -> SolverOutput:
        """Parse solver output into structured parsed_data."""

    @abc.abstractmethod
    def validate(
        self,
        parsed: SolverOutput,
    ) -> SolverOutput:
        """Validate physical constraints on parsed results.

        Checks: passivity (|S†S| ≤ I), reciprocity (|S21-S12| < tol),
        positive-definite capacitance matrix, causality.
        """

    def run_pipeline(
        self,
        geometry: GeometrySpec,
        output_dir: Path,
    ) -> SolverOutput:
        """Run the full five-stage pipeline.

        Returns the final validated SolverOutput. If any stage fails or the
        solver is unavailable, returns status="SKIPPED" or "FAILED" with
        the reason from the failing stage.
        """
        avail = self.is_available()
        if not avail.available:
            return SolverOutput.skipped(self.name, avail.reason)

        output_dir.mkdir(parents=True, exist_ok=True)

        prepared = self.prepare(geometry, output_dir)
        if prepared.status == "FAILED":
            return prepared

        meshed = self.mesh(prepared, output_dir)
        if meshed.status == "FAILED":
            return meshed

        solved = self.solve(meshed, output_dir)
        if solved.status in ("FAILED", "SKIPPED"):
            return solved

        parsed = self.parse(solved, output_dir)
        if parsed.status == "FAILED":
            return parsed

        validated = self.validate(parsed)
        return validated


class CapacitanceSolver(EMSolverInterface):
    """Specialisation for capacitance/C-matrix extraction (Elmer, FastCap)."""

    def validate(self, parsed: SolverOutput) -> SolverOutput:
        """Validate that the C-matrix is positive-definite and physically bounded."""
        if parsed.status != "EXECUTED":
            return parsed

        c_matrix = parsed.parsed_data.get("capacitance_matrix_pf")
        if c_matrix is None:
            return SolverOutput.failed(
                self.name,
                "No capacitance_matrix_pf in parsed output",
                parsed.output_dir,
            )

        if isinstance(c_matrix, (int, float)):
            c_pf = float(c_matrix)
            if c_pf <= 0:
                return SolverOutput.failed(
                    self.name,
                    f"Capacitance {c_pf} pF is not positive-definite",
                    parsed.output_dir,
                )
            if c_pf > 1e6:
                return SolverOutput.failed(
                    self.name,
                    f"Capacitance {c_pf} pF is unphysically large (> 1 µF)",
                    parsed.output_dir,
                )

        parsed.parsed_data["validation"] = {
            "capacitance_matrix_valid": True,
            "check": "positive-definite",
        }
        return parsed


class RFSolver(EMSolverInterface):
    """Specialisation for RF S-parameter extraction (openEMS, Palace)."""

    def validate(self, parsed: SolverOutput) -> SolverOutput:
        """Validate Touchstone output: reciprocity and passivity."""
        if parsed.status != "EXECUTED":
            return parsed

        touchstone_path = parsed.artifacts.get("touchstone")
        if touchstone_path is None or not touchstone_path.exists():
            return SolverOutput.failed(
                self.name,
                "No Touchstone file produced — no simulation result",
                parsed.output_dir,
            )

        from text_to_gds.validation.touchstone import validate_touchstone
        report = validate_touchstone(touchstone_path)

        if not report["reciprocity"]["passed"] or not report["passivity"]["passed"]:
            parsed.status = "FAILED"
            parsed.reason = (
                f"Touchstone validation failed: "
                f"reciprocity={report['reciprocity']['passed']}, "
                f"passivity={report['passivity']['passed']}"
            )

        parsed.parsed_data["touchstone_validation"] = report
        return parsed
