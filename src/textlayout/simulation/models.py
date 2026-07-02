"""Structured simulation status and readiness records."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def target_comparison(
    value: float, target: float | None, tolerance_pct: float, quantity: str
) -> dict[str, Any] | None:
    """The one shared extracted-vs-target comparison record for solver results.

    Returns ``None`` when no target was stated (nothing to compare against);
    ``within_tolerance`` here feeds :attr:`SimulationResult.physics_verified`.
    """
    if target is None or target == 0:
        return None
    error_pct = 100.0 * (value - target) / target
    return {
        "quantity": quantity,
        "extracted": value,
        "target": target,
        "error_pct": round(error_pct, 3),
        "tolerance_pct": tolerance_pct,
        "within_tolerance": abs(error_pct) <= tolerance_pct,
    }


READINESS_LABELS = {
    0: "analytical estimate only",
    1: "geometry generated and verified",
    2: "open-source simulation input prepared",
    3: "simulation result generated",
    4: "result compared against target",
    5: "optimization loop implemented",
}

# The execution-evidence ladder. Each adapter advances through these stages; the
# stage is *derived* from the result's status/contents so it can never disagree
# with the artifacts on disk.
EVIDENCE_STAGES = (
    "solver_missing",
    "input_prepared",
    "executed",
    "parsed",
    "compared",
    "failed_gracefully",
)


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """Honest record of preparation or execution of a physics solver."""

    status: str
    solver: str
    readiness_level: int
    reason: str
    output_dir: Path | None = None
    artifacts: dict[str, str] = field(default_factory=dict)
    extracted_quantities: dict[str, Any] = field(default_factory=dict)
    target_comparison: dict[str, Any] | None = None
    warnings: tuple[str, ...] = ()
    command: tuple[str, ...] = ()
    return_code: int | None = None
    runtime_seconds: float | None = None
    evidence_level: str | None = None
    solver_version: str | None = None

    @property
    def readiness_label(self) -> str:
        return READINESS_LABELS[self.readiness_level]

    @property
    def evidence_stage(self) -> str:
        """Position on the execution-evidence ladder, derived from artifacts.

        Maps the internal status (kept stable for backward compatibility) onto
        the explicit ``solver_missing | input_prepared | executed | parsed |
        compared | failed_gracefully`` vocabulary.
        """
        if self.status == "skipped":
            return "solver_missing"
        if self.status == "failed":
            return "failed_gracefully"
        if self.status == "executed":
            if self.target_comparison is not None:
                return "compared"
            if self.extracted_quantities:
                return "parsed"
            return "executed"
        return "input_prepared"

    @property
    def solver_executed(self) -> bool:
        return self.status == "executed"

    @property
    def physics_verified(self) -> bool:
        """Only true with a real run, a parsed value, and an in-tolerance compare.

        This is the single gate that downstream code must use before claiming a
        target was met. A prepared input or an analytical estimate can never make
        it true."""
        return (
            self.status == "executed"
            and bool(self.extracted_quantities)
            and self.target_comparison is not None
            and bool(self.target_comparison.get("within_tolerance"))
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "evidence_stage": self.evidence_stage,
            "solver": self.solver,
            "solver_executed": self.solver_executed,
            "physics_verified": self.physics_verified,
            "readiness_level": self.readiness_level,
            "readiness_label": self.readiness_label,
            "reason": self.reason,
            "output_dir": str(self.output_dir) if self.output_dir is not None else None,
            "artifacts": dict(self.artifacts),
            "extracted_quantities": dict(self.extracted_quantities),
            "target_comparison": self.target_comparison,
            "warnings": list(self.warnings),
            "command": list(self.command),
            "return_code": self.return_code,
            "runtime_seconds": self.runtime_seconds,
            "evidence_level": self.evidence_level,
            "solver_version": self.solver_version,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Simulation Plan",
            "",
            f"- Solver: **{self.solver}**",
            f"- Status: **{self.status}**",
            f"- Readiness: **Level {self.readiness_level} - {self.readiness_label}**",
            f"- Reason: {self.reason}",
            "",
        ]
        if self.artifacts:
            lines += ["## Prepared artifacts", ""]
            lines += [f"- `{name}`: `{path}`" for name, path in self.artifacts.items()]
            lines.append("")
        if self.extracted_quantities:
            lines += ["## Extracted quantities", ""]
            lines += [f"- `{name}`: `{value}`" for name, value in self.extracted_quantities.items()]
            lines.append("")
        if self.warnings:
            lines += ["## Limitations", ""]
            lines += [f"- {warning}" for warning in self.warnings]
            lines.append("")
        lines += [
            "## Status contract",
            "",
            "`input_files_prepared` is not a simulation result. Only `executed` with a "
            "non-empty solver-owned output is simulation evidence.",
            "",
        ]
        return "\n".join(lines)
