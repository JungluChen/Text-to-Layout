"""Structured simulation status and readiness records."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

READINESS_LABELS = {
    0: "analytical estimate only",
    1: "geometry generated and verified",
    2: "open-source simulation input prepared",
    3: "simulation result generated",
    4: "result compared against target",
    5: "optimization loop implemented",
}


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
    warnings: tuple[str, ...] = ()
    command: tuple[str, ...] = ()

    @property
    def readiness_label(self) -> str:
        return READINESS_LABELS[self.readiness_level]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "solver": self.solver,
            "readiness_level": self.readiness_level,
            "readiness_label": self.readiness_label,
            "reason": self.reason,
            "output_dir": str(self.output_dir) if self.output_dir is not None else None,
            "artifacts": dict(self.artifacts),
            "extracted_quantities": dict(self.extracted_quantities),
            "warnings": list(self.warnings),
            "command": list(self.command),
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
