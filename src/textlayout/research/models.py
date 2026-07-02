"""Value objects for the research/evidence layer.

A :class:`ResearchReport` is the evidence backbone of the pipeline: it records
the first-principles model, the equations, the assumptions, the literature
references, the analytical estimate(s), the design rationale, the limitations,
and the recommended simulation — everything needed to justify *why* a generated
geometry should work, before any EM solve.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Equation:
    name: str
    expression: str
    description: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "expression": self.expression, "description": self.description}


@dataclass(frozen=True, slots=True)
class Reference:
    citation: str
    note: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"citation": self.citation, "note": self.note}


@dataclass(frozen=True, slots=True)
class ResearchReport:
    """Evidence package for one component/target."""

    component: str
    model_name: str
    physical_target: Mapping[str, float] = field(default_factory=dict)
    equations: tuple[Equation, ...] = ()
    assumptions: tuple[str, ...] = ()
    references: tuple[Reference, ...] = ()
    analytical_estimates: Mapping[str, Any] = field(default_factory=dict)
    design_notes: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    simulation_recommendation: Mapping[str, str] = field(default_factory=dict)
    proposed_parameters: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "model_name": self.model_name,
            "physical_target": dict(self.physical_target),
            "equations": [e.to_dict() for e in self.equations],
            "assumptions": list(self.assumptions),
            "references": [r.to_dict() for r in self.references],
            "analytical_estimates": dict(self.analytical_estimates),
            "design_notes": list(self.design_notes),
            "limitations": list(self.limitations),
            "simulation_recommendation": dict(self.simulation_recommendation),
            "proposed_parameters": (
                dict(self.proposed_parameters) if self.proposed_parameters is not None else None
            ),
        }

    def to_markdown(self) -> str:
        lines: list[str] = [f"# Evidence — {self.component}", ""]
        lines.append(f"**Model:** {self.model_name}")
        if self.physical_target:
            tgt = ", ".join(f"{k} = {v}" for k, v in self.physical_target.items())
            lines.append(f"**Target:** {tgt}")
        lines.append("")

        if self.analytical_estimates:
            lines += ["## Analytical estimate", ""]
            for k, v in self.analytical_estimates.items():
                lines.append(f"- `{k}` = {v}")
            lines.append("")

        if self.equations:
            lines += ["## First-principles equations", ""]
            for e in self.equations:
                lines.append(
                    f"- **{e.name}:** `{e.expression}`"
                    + (f" — {e.description}" if e.description else "")
                )
            lines.append("")

        if self.proposed_parameters is not None:
            lines += ["## Proposed parameters (from target)", "", "```json"]
            import json

            lines.append(json.dumps(dict(self.proposed_parameters), indent=2))
            lines += ["```", ""]

        for title, items in (
            ("Design rationale", self.design_notes),
            ("Assumptions", self.assumptions),
            ("Limitations", self.limitations),
        ):
            if items:
                lines += [f"## {title}", ""]
                lines += [f"- {item}" for item in items]
                lines.append("")

        if self.simulation_recommendation:
            lines += ["## Recommended simulation", ""]
            for k, v in self.simulation_recommendation.items():
                lines.append(f"- **{k}:** {v}")
            lines.append("")

        if self.references:
            lines += ["## References", ""]
            for r in self.references:
                lines.append(f"- {r.citation}" + (f" — {r.note}" if r.note else ""))
            lines += ["", "See the repository [REFERENCES.md](../../../REFERENCES.md).", ""]

        lines += [
            "## Evidence status",
            "",
            "- A citation supports the analytical **method/model**, not this specific layout.",
            "- This generated geometry has **not** been EM-simulated (no solver executed).",
            "- This generated geometry has **not** been measured.",
            "- This generated geometry is **not** fabrication-ready.",
            "",
        ]

        return "\n".join(lines).rstrip() + "\n"

    def analytical_estimate_markdown(self) -> str:
        """Render the equation-backed estimate separately for benchmark packets."""
        lines = [
            f"# Analytical Estimate - {self.component}",
            "",
            f"- Model: **{self.model_name}**",
            "- Status: **analytical** (not simulated or measured)",
            "",
            "## Target",
            "",
        ]
        lines += [f"- `{name}`: `{value}`" for name, value in self.physical_target.items()]
        lines += ["", "## Calculated values", ""]
        lines += [f"- `{name}`: `{value}`" for name, value in self.analytical_estimates.items()]
        lines += ["", "## Equations", ""]
        lines += [
            f"- **{equation.name}:** `{equation.expression}`"
            + (f" - {equation.description}" if equation.description else "")
            for equation in self.equations
        ]
        lines += ["", "## Assumptions", ""]
        lines += [f"- {item}" for item in self.assumptions]
        lines += ["", "## Limitations", ""]
        lines += [f"- {item}" for item in self.limitations]
        return "\n".join(lines).rstrip() + "\n"

    def simulation_plan_markdown(self) -> str:
        """Render the pre-execution solver plan without implying a result."""
        lines = [
            f"# Simulation Plan - {self.component}",
            "",
            "- Status: **planned**",
            "- Simulation readiness: **Level 1 - geometry/research workflow defined**",
            "- No solver result is claimed by this file.",
            "",
            "## Recommended extraction",
            "",
        ]
        lines += [
            f"- **{quantity}:** {recommendation}"
            for quantity, recommendation in self.simulation_recommendation.items()
        ]
        lines += [
            "",
            "## Comparison method",
            "",
            "1. Execute the named solver and retain its input, version, log, and output artifact.",
            "2. Extract the requested physical quantity from the solver-owned output.",
            "3. Compare it with the Layout DSL target and state the error and tolerance.",
            "4. Change Layout DSL parameters, regenerate, and rerun verification.",
            "",
            "## Limitations",
            "",
        ]
        lines += [f"- {item}" for item in self.limitations]
        return "\n".join(lines).rstrip() + "\n"
