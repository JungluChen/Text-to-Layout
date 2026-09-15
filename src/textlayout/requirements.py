"""Strict electrical goals for AI callers that do not choose a device template.

The selected topology is an explicit, inspectable starting choice. Unknown
requirements fail validation; no arbitrary text is silently treated as a rule.
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import replace
import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from textlayout.prompt import DesignIntent
from textlayout.errors import InvalidParametersError
from textlayout.verification import Check, CheckStatus, VerificationReport
from textlayout.workflows.from_text import FromTextResult
from textlayout.workflows.generate import GenerateWorkflow

PositiveFinite = Annotated[float, Field(gt=0, allow_inf_nan=False, strict=True)]
Quantity = Literal["capacitance_pf", "inductance_nh", "impedance_ohm", "quarter_wave_frequency_ghz"]

_CHOICES: dict[str, tuple[str, str]] = {
    "capacitance_pf": ("IDC", "A planar interdigitated capacitor provides two accessible nets "
                       "and tunable overlap without requiring a dielectric-layer process."),
    "inductance_nh": ("SpiralInductor", "A square spiral provides a compact planar inductance "
                     "seed with a supported FastHenry extraction path."),
    "impedance_ohm": ("CPW", "A coplanar waveguide keeps signal and ground on one layer and "
                     "allows impedance synthesis under width and gap constraints."),
    "quarter_wave_frequency_ghz": ("QuarterWaveResonator", "The requested quarter-wave topology "
                                  "sets an initial electrical length from phase velocity."),
}


class DesignRequirements(BaseModel):
    """One physical goal with explicit units and enforceable geometry limits."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    quantity: Quantity
    value: PositiveFinite
    technology: str = "generic_2metal"
    operating_frequency_ghz: PositiveFinite | None = Field(
        default=None, description="Operating context for research; not a verified bandwidth rating")
    min_width_um: PositiveFinite | None = None
    min_gap_um: PositiveFinite | None = None
    max_bbox_width_um: PositiveFinite | None = None
    max_bbox_height_um: PositiveFinite | None = None
    tolerance_percent: PositiveFinite = 5.0

    @model_validator(mode="after")
    def consistent_frequency(self) -> DesignRequirements:
        if self.quantity == "quarter_wave_frequency_ghz" and self.operating_frequency_ghz is not None:
            if self.operating_frequency_ghz != self.value:
                raise ValueError("Quarter-wave target and operating frequency must agree")
        return self

    def design_intent(self, workflow: GenerateWorkflow) -> DesignIntent:
        technology = workflow.technology(self.technology)
        component, reason = _CHOICES[self.quantity]
        target_key = "frequency_ghz" if self.quantity == "quarter_wave_frequency_ghz" else self.quantity
        target = {target_key: self.value}
        if self.operating_frequency_ghz is not None:
            target["frequency_ghz"] = self.operating_frequency_ghz
        constraints = {key: value for key in (
            "min_width_um", "min_gap_um", "max_bbox_width_um", "max_bbox_height_um"
        ) if (value := getattr(self, key)) is not None}
        constraints["min_width_um"] = max(self.min_width_um or 0, technology.min_width_for("M1"))
        constraints["min_gap_um"] = max(self.min_gap_um or 0, technology.min_spacing_for("M1"))
        parameters: dict[str, float | int] = {}
        if component == "SpiralInductor":
            parameters = {"turns": 4,
                          "trace_width_um": max(4.0, self.min_width_um or 0,
                                                technology.min_width_for("M1")),
                          "spacing_um": max(2.0, self.min_gap_um or 0,
                                            technology.min_spacing_for("M1"))}
        if component == "CPW" and self.max_bbox_height_um is not None:
            parameters["length_um"] = min(1000.0, self.max_bbox_height_um)
        return DesignIntent(
            prompt=f"Design for {self.value:g} {self.quantity} with typed requirements",
            component=component, technology=self.technology, target=target,
            constraints=constraints, parameters=parameters,
            notes=[reason, "Topology selected from supported templates; no global optimum is claimed."])


def run_requirements(
    requirements: DesignRequirements,
    output_dir: str | Path,
    *,
    workflow: GenerateWorkflow,
    execute_solver: bool = True,
    solver_executable: str | None = None,
) -> FromTextResult:
    """Use the same graph, GDS checks, retuning loop and evidence as text requests."""
    from textlayout.workflow.graph import run_prompt_workflow
    from textlayout.workflows.from_text import size_parameters, write_json

    out = Path(output_dir)
    intent = requirements.design_intent(workflow)
    write_json(out / "requirements.json", requirements.model_dump(mode="json"))
    try:
        # Reject unreachable bounded optimizations before expensive polygon
        # verification/export. This is a feasibility check, not solver evidence.
        sizing = size_parameters(intent, workflow.technology(requirements.technology),
                                 tolerance_percent=requirements.tolerance_percent)
        if sizing.optimization is not None and not sizing.optimization.converged:
            write_json(out / "requirements_feasibility.json", sizing.optimization.model_dump(mode="json"))
            raise InvalidParametersError(intent.component,
                "Target is unreachable within the supported sizing bounds; "
                f"best estimate {sizing.optimization.estimated_capacitance_pf:g} pF. "
                "See requirements_feasibility.json for the bounded search record.")
        result = run_prompt_workflow(
            workflow, intent.prompt, out, tolerance_percent=requirements.tolerance_percent,
            execute_solver=execute_solver, solver_executable=solver_executable, design_intent=intent)
    except ValueError as exc:
        raise InvalidParametersError(intent.component, str(exc)) from exc
    from textlayout.research.design_rules import design_rules_for

    keys = {"capacitance_pf": "estimated_capacitance_pf", "inductance_nh": "estimated_inductance_nh",
            "impedance_ohm": "estimated_z0_ohm", "quarter_wave_frequency_ghz": "frequency_ghz"}
    extracted = result.evidence.extracted_value
    estimate = result.generate.geometry.metadata.get(keys[requirements.quantity])
    if requirements.quantity == "quarter_wave_frequency_ghz":
        from textlayout.research.formulas import cpw_eps_eff

        eps_eff = cpw_eps_eff(workflow.technology(requirements.technology).substrate_epsilon_r)
        estimate = 299792458 / (4 * float(result.spec.parameters["length_um"]) * 1e-6
                                * math.sqrt(eps_eff)) / 1e9
    value = extracted if extracted is not None else estimate
    error = (100 * abs(float(value) - requirements.value) / requirements.value
             if isinstance(value, (int, float)) and math.isfinite(value) else None)
    passed = error is not None and error <= requirements.tolerance_percent
    basis = "solver extraction" if extracted is not None else "analytical estimate"
    check = Check("requirements_target", CheckStatus.PASS if passed else CheckStatus.FAIL,
                  f"{basis}: error={error!r}%, tolerance={requirements.tolerance_percent:g}%",
                  value=error, limit=requirements.tolerance_percent, unit="percent")
    report = VerificationReport.from_checks(result.generate.report.component,
                                            (*result.generate.report.checks, check))
    result = replace(result, generate=replace(result.generate, report=report))
    verification = report.to_dict()
    verification["target_basis"] = basis
    files = dict(result.files)
    files["requirements"] = str(out / "requirements.json")
    files["requirements_verification"] = write_json(out / "requirements_verification.json", verification)
    files["design_review"] = write_json(out / "design_review.json", {
        "schema": "textlayout.design-review.v1", "requirements": requirements.model_dump(mode="json"),
        "intent": result.intent.model_dump(mode="json"), "layout_requirements_passed": result.ok,
        "target_basis": basis, "verification": verification,
        "acceptance_scope": "Primary electrical target under the stated model, plus width/gap "
                            "and footprint checks; not a process or operating-bandwidth qualification",
        "operating_bandwidth_verified": False,
        "chosen_parameters": result.spec.parameters,
        "first_principles": result.generate.research.to_dict(),
        "engineering_rules": design_rules_for(result.intent.component),
        "simulation_status": result.evidence.status.value, "fabrication_ready": False,
    })
    # The graph wrote these artifacts before the electrical-goal check. Publish
    # the final verdict everywhere so consumers cannot read a stale PASS from
    # verification.json or report.md after the requested target has failed.
    from textlayout.evidence import EvidenceStatus
    from textlayout.workflows.from_text import render_jpa_report

    files["verification"] = write_json(out / "verification.json", verification)
    report_path = out / "report.md"
    report_path.write_text(render_jpa_report(
        result.intent, result.spec, result.generate, result.optimization,
        result.evidence, result.circuit_simulations, files, jpa_sizing=None,
        physics_verified=result.ok and result.evidence.status == EvidenceStatus.PHYSICS_VERIFIED,
    ), encoding="utf-8")
    files["report"] = str(report_path)
    return replace(result, files=files)
