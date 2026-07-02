"""FromTextWorkflow — natural-language prompt → closed-loop verified artifacts.

The full pipeline behind ``textlayout prompt`` and ``POST /layout/from-text``:

    prompt
      → DesignIntent (deterministic parser; intent.json)
      → closed-loop analytical tuning        (optimization.json)
      → Layout DSL                           (layout.json)
      → geometry + verification + export     (output.gds/.svg, verification.json)
      → solver input prep + guarded run      (simulation.json — typed evidence)
      → honest report                        (report.md)

Every simulation claim flows through :class:`~textlayout.evidence.QuantityEvidence`,
so the report can never say more than the artifacts prove.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from textlayout.evidence import EvidenceStatus, QuantityEvidence
from textlayout.optimization import IDCOptimizationResult, optimize_idc
from textlayout.prompt import DesignIntent, parse_prompt
from textlayout.research import formulas as F
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation import simulate_layout
from textlayout.simulation.evidence_map import capacitance_evidence, quantity_evidence
from textlayout.workflows.generate import GenerateResult, GenerateWorkflow

FROM_TEXT_SCHEMA = "textlayout.from-text.v1"

_ANALYTICAL_MODEL_IDC = "Bahl/Alley quasi-static closed form (Bahl 2003, Alley 1970)"


@dataclass(frozen=True, slots=True)
class FromTextResult:
    """Everything the text entry point produced, plus where it lives on disk."""

    intent: DesignIntent
    spec: LayoutSpec
    generate: GenerateResult
    evidence: QuantityEvidence
    optimization: IDCOptimizationResult | None
    output_dir: Path
    files: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.generate.report.passed

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": FROM_TEXT_SCHEMA,
            "status": "ok" if self.ok else "verification_failed",
            "component": self.spec.component,
            "target": dict(self.spec.target),
            "simulation_status": self.evidence.status.value,
            "simulation_summary": self.evidence.summary_line(),
            "artifacts": {name: Path(p).name for name, p in self.files.items()},
            "output_dir": str(self.output_dir),
        }


class FromTextWorkflow:
    """Drives the prompt → artifacts loop on top of a :class:`GenerateWorkflow`."""

    def __init__(self, generate_workflow: GenerateWorkflow) -> None:
        self._generate = generate_workflow

    def run(
        self,
        prompt: str,
        output_dir: str | Path,
        *,
        tolerance_percent: float = 5.0,
        execute_solver: bool = True,
        solver_executable: str | None = None,
    ) -> FromTextResult:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        files: dict[str, str] = {}

        intent = parse_prompt(prompt)
        files["intent"] = _write_json(out / "intent.json", intent.model_dump(mode="json"))

        technology = self._generate.technology(intent.technology)
        optimization: IDCOptimizationResult | None = None
        parameters: dict[str, Any] = dict(intent.parameters)
        if intent.component == "IDC" and "capacitance_pf" in intent.target:
            optimization = optimize_idc(
                target_capacitance_pf=intent.target["capacitance_pf"],
                substrate_epsilon_r=technology.substrate_epsilon_r,
                min_finger_width_um=intent.constraints.get(
                    "min_width_um", technology.min_width_for("M1")
                ),
                min_gap_um=intent.constraints.get(
                    "min_gap_um", technology.min_spacing_for("M1")
                ),
                initial_parameters=intent.parameters,
                tolerance_percent=tolerance_percent,
            )
            parameters = dict(optimization.final_parameters)
        elif intent.component == "IDC":
            parameters = {
                "finger_pairs": 10,
                "finger_width_um": 4.0,
                "gap_um": 2.0,
                "overlap_um": 250.0,
                "bus_width_um": 25.0,
                **parameters,
            }
        elif intent.component == "CPW":
            width = 10.0
            target_z0 = intent.target.get("impedance_ohm", 50.0)
            parameters = {
                "center_width_um": width,
                "gap_um": round(F.cpw_gap_for_z0(target_z0, width, technology.substrate_epsilon_r), 4),
                "length_um": 1000.0,
                **{k: v for k, v in parameters.items() if k in {"gap_um"}},
            }
        elif intent.component == "SpiralInductor":
            turns = int(parameters.get("turns", 4))
            width = 5.0
            spacing = 3.0
            target_nh = intent.target.get("inductance_nh")
            outer = _spiral_outer_for_target(turns, width, spacing, target_nh)
            parameters = {
                "turns": turns,
                "outer_dimension_um": round(outer, 4),
                "trace_width_um": width,
                "spacing_um": spacing,
                "thickness_um": 0.2,
            }
        elif intent.component == "QuarterWaveResonator":
            frequency = intent.target.get("frequency_ghz", 6.0)
            length = F.cpw_quarter_wave_length_um(
                frequency, F.cpw_eps_eff(technology.substrate_epsilon_r)
            )
            parameters = {
                "center_width_um": 10.0,
                "gap_um": 6.0,
                "length_um": round(length, 4),
                "coupling_gap_um": 4.0,
            }
        elif intent.component == "SQUID":
            parameters = {
                "loop_inner_width_um": 20.0,
                "loop_inner_height_um": 20.0,
                "trace_width_um": 2.0,
                "junction_gap_um": 1.0,
                "junction_width_um": 1.0,
                **parameters,
            }
        if optimization is not None:
            files["optimization"] = _write_json(
                out / "optimization.json", optimization.model_dump(mode="json")
            )
        else:
            files["optimization"] = _write_json(
                out / "optimization.json",
                {
                    "schema": "textlayout.analytical-sizing.v1",
                    "component": intent.component,
                    "method": "deterministic analytical sizing",
                    "target": dict(intent.target),
                    "final_parameters": dict(parameters),
                    "solver_executed": False,
                },
            )

        spec = LayoutSpec(
            component=intent.component,
            technology=intent.technology,
            target=dict(intent.target),
            parameters=parameters,
            rules=dict(intent.constraints),
            outputs={"gds": True, "svg": True, "json": False},
            metadata={"prompt": intent.prompt, "intent_schema": intent.schema_version},
        )
        files["layout"] = _write_json(out / "layout.json", spec.model_dump(mode="json"))

        result = self._generate.run(spec, output_dir=out, stem="output")
        files["verification"] = _write_json(out / "verification.json", result.report.to_dict())
        files.update({k: v for k, v in result.files.items() if k in {"gds", "svg"}})

        evidence = self._simulate(
            intent, spec, result, out,
            tolerance_percent=tolerance_percent,
            execute_solver=execute_solver,
            solver_executable=solver_executable,
        )
        files["simulation"] = _write_json(
            out / "simulation.json",
            {
                "schema": "textlayout.simulation-evidence.v1",
                "evidence": [json.loads(evidence.model_dump_json())],
            },
        )

        report_path = out / "report.md"
        report_path.write_text(
            _render_report(intent, spec, result, optimization, evidence, files),
            encoding="utf-8",
        )
        files["report"] = str(report_path)

        return FromTextResult(
            intent=intent,
            spec=spec,
            generate=result,
            evidence=evidence,
            optimization=optimization,
            output_dir=out,
            files=files,
        )

    def _simulate(
        self,
        intent: DesignIntent,
        spec: LayoutSpec,
        result: GenerateResult,
        out: Path,
        *,
        tolerance_percent: float,
        execute_solver: bool,
        solver_executable: str | None,
    ) -> QuantityEvidence:
        target_c = intent.target.get("capacitance_pf")
        analytical = result.research.analytical_estimates.get("estimated_capacitance_pf")
        analytical_value = float(analytical) if isinstance(analytical, (int, float)) else None

        if not result.report.passed:
            return QuantityEvidence(
                quantity="capacitance",
                target_value=target_c,
                target_unit="pF" if target_c is not None else None,
                analytical_value=analytical_value,
                analytical_model=_ANALYTICAL_MODEL_IDC if analytical_value is not None else None,
                tolerance_percent=tolerance_percent,
                status=EvidenceStatus.FAILED,
                notes=["Geometry verification failed; simulation was not attempted."],
            )

        simulation = simulate_layout(
            spec,
            result.geometry,
            self._generate.technology(spec.technology),
            out / "simulation",
            solver="auto",
            execute=execute_solver,
            executable=solver_executable,
        )
        if intent.component == "IDC":
            return capacitance_evidence(
                simulation,
                target_capacitance_pf=target_c,
                tolerance_percent=tolerance_percent,
                analytical_value_pf=analytical_value,
                analytical_model=_ANALYTICAL_MODEL_IDC,
            )
        evidence_config = {
            "CPW": (
                "characteristic_impedance", "characteristic_impedance_ohm", "ohm",
                intent.target.get("impedance_ohm"), "estimated_z0_ohm",
                "textlayout.simulation.runners.extract_cpw_from_touchstone",
            ),
            "SpiralInductor": (
                "inductance", "inductance_nh", "nH", intent.target.get("inductance_nh"),
                "estimated_inductance_nh", "textlayout.simulation.runners.parse_fasthenry_inductance",
            ),
            "QuarterWaveResonator": (
                "resonance_frequency", "resonance_frequency_ghz", "GHz",
                intent.target.get("frequency_ghz"), "target_frequency_ghz",
                "textlayout.simulation.runners.extract_resonance_from_touchstone",
            ),
            "SQUID": (
                "mean_voltage", "mean_voltage_uv", "uV", intent.target.get("voltage_uv"),
                "josephson_inductance_ph_per_junction", "textlayout.simulation.josim.parse_josim_csv",
            ),
        }
        quantity, key, unit, target, estimate_key, parser = evidence_config[intent.component]
        return quantity_evidence(
            simulation,
            quantity=quantity,
            extracted_key=key,
            unit=unit,
            target_value=target,
            tolerance_percent=tolerance_percent,
            parser=parser,
            analytical_value=_first_float(result.research.analytical_estimates, estimate_key),
            analytical_model=result.research.model_name,
        )


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _first_float(mapping: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _spiral_outer_for_target(
    turns: int, width_um: float, spacing_um: float, target_nh: float | None
) -> float:
    minimum = 2.0 * turns * width_um + 2.0 * (turns - 1) * spacing_um + 1.0
    if target_nh is None:
        return max(200.0, minimum)
    lo, hi = minimum, max(500.0, minimum * 2.0)
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        inner = mid - 2.0 * turns * width_um - 2.0 * (turns - 1) * spacing_um
        estimate = F.spiral_inductance_nh(turns, mid, inner)
        if estimate < target_nh:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


_STATUS_EXPLANATIONS = {
    EvidenceStatus.SKIPPED_SOLVER_ABSENT: (
        "The solver is not installed; solver input files were prepared but **no "
        "physics verification was performed**."
    ),
    EvidenceStatus.SIMULATION_INPUT_PREPARED: (
        "Solver input files were prepared but the solver was not executed; **no "
        "physics verification was performed**."
    ),
    EvidenceStatus.SIMULATION_EXECUTED: (
        "The solver executed and a value was extracted, but the result does not "
        "meet tolerance (or no target was stated) — **not physics verified**."
    ),
    EvidenceStatus.PHYSICS_VERIFIED: (
        "The solver executed, its output was parsed, and the extracted value is "
        "within tolerance of the target."
    ),
    EvidenceStatus.FAILED: "The solver run failed; see notes. **No verified value exists.**",
    EvidenceStatus.ANALYTICAL_ONLY: (
        "Only an analytical formula was used. **This is not a solver result.**"
    ),
}


def _render_report(
    intent: DesignIntent,
    spec: LayoutSpec,
    result: GenerateResult,
    optimization: IDCOptimizationResult | None,
    evidence: QuantityEvidence,
    files: dict[str, str],
) -> str:
    geometry_pass = result.report.passed
    lines = [
        f"# Text-to-Layout Report — {spec.component}",
        "",
        f"Prompt: `{intent.prompt}`",
        "",
        "## Status summary",
        "",
        f"- Geometry verification: **{'PASS' if geometry_pass else 'FAIL'}**",
        f"- DRC-like checks: **{'PASS' if geometry_pass else 'FAIL'}** "
        f"({sum(1 for c in result.report.checks)} checks)",
        f"- Simulation status: **{evidence.status.value}**",
        "",
        _STATUS_EXPLANATIONS[evidence.status],
        "",
        "## Target vs result",
        "",
        "| Quantity | Target | Analytical estimate | Solver-extracted | Error vs target | Status |",
        "| - | - | - | - | - | - |",
    ]
    target = (
        f"{evidence.target_value} {evidence.target_unit}"
        if evidence.target_value is not None
        else "—"
    )
    analytical = (
        f"{evidence.analytical_value}" if evidence.analytical_value is not None else "—"
    )
    extracted = (
        f"{evidence.extracted_value} {evidence.extracted_unit}"
        if evidence.extracted_value is not None
        else "— (no solver result)"
    )
    error = f"{evidence.error_percent}%" if evidence.error_percent is not None else "—"
    lines.append(
        f"| {evidence.quantity} | {target} | {analytical} | {extracted} | {error} "
        f"| {evidence.status.value} |"
    )
    lines += ["", f"> {evidence.summary_line()}", ""]

    if optimization is not None:
        lines += [
            "## Closed-loop analytical tuning",
            "",
            f"- Converged: **{optimization.converged}** in {len(optimization.iterations)} "
            f"iteration(s) (tolerance {optimization.tolerance_percent}%)",
            f"- Final parameters: `{json.dumps(optimization.final_parameters)}`",
            f"- Analytical estimate: {optimization.estimated_capacitance_pf} pF vs "
            f"target {optimization.target_capacitance_pf} pF "
            f"(error {optimization.error_percent}%)",
            "- The optimizer uses the analytical model only; it never claims physics "
            "verification.",
            "",
        ]

    lines += ["## Verification checks", ""]
    for check in result.report.checks:
        suffix = f": {check.message}" if check.message else ""
        lines.append(f"- `{check.status.value.upper()}` {check.name}{suffix}")

    lines += ["", "## Artifacts", ""]
    for kind, filename in sorted(files.items()):
        lines.append(f"- `{kind}`: `{Path(filename).name}`")

    if evidence.notes:
        lines += ["", "## Notes", ""]
        lines += [f"- {note}" for note in evidence.notes]

    lines += [
        "",
        "## Limitations",
        "",
        "- This design is **not fabrication-ready**. Process-specific DRC, EM "
        "cross-check, and expert review are required before tapeout.",
    ]
    return "\n".join(lines).rstrip() + "\n"
