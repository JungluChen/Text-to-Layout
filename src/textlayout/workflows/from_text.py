"""One credible natural-language-to-IDC closed-loop workflow."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from textlayout.evidence_contract import EvidenceStatus, ExtractedValueEvidence
from textlayout.optimization import IDCOptimizationResult, optimize_idc
from textlayout.prompt import PromptIntent, cpw_spec_from_intent, parse_prompt
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation import prepare_idc_fastercap, run_fastercap


@dataclass(frozen=True, slots=True)
class FromTextResult:
    intent: PromptIntent
    spec: LayoutSpec
    files: dict[str, str]
    verification: dict[str, Any]
    simulation: dict[str, Any]
    optimization: IDCOptimizationResult | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.to_dict(),
            "layout": self.spec.model_dump(mode="json"),
            "files": self.files,
            "verification": self.verification,
            "simulation": self.simulation,
            "optimization": None if self.optimization is None else self.optimization.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class CompiledText:
    """Auditable prompt compilation result before geometry or file writes."""

    intent: PromptIntent
    spec: LayoutSpec
    optimization: IDCOptimizationResult | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "ready",
            "intent": self.intent.to_dict(),
            "assumptions": list(self.intent.assumptions),
            "unresolved_questions": [],
            "layout": self.spec.model_dump(mode="json"),
            "optimization": None if self.optimization is None else self.optimization.to_dict(),
        }


def compile_text(prompt: str, *, analytical_tolerance_pct: float = 1.0) -> CompiledText:
    """Compile text into a typed DSL without generating or writing artifacts."""
    intent = parse_prompt(prompt)
    optimization: IDCOptimizationResult | None = None
    if intent.component == "IDC":
        assert intent.target_capacitance_pf is not None
        explicit = (
            intent.finger_pairs,
            intent.finger_width_um,
            intent.gap_um,
            intent.overlap_um,
        )
        if all(value is not None for value in explicit):
            assert intent.finger_pairs is not None
            assert intent.finger_width_um is not None
            assert intent.gap_um is not None
            assert intent.overlap_um is not None
            width = float(intent.finger_width_um)
            parameters: dict[str, float | int | str] = {
                "finger_pairs": int(intent.finger_pairs),
                "finger_width_um": width,
                "gap_um": float(intent.gap_um),
                "overlap_um": float(intent.overlap_um),
                "bus_width_um": intent.bus_width_um or max(10.0, 5.0 * width),
                "metal_layer": "M1",
            }
        else:
            seed = {
                key: value
                for key, value in {
                    "finger_pairs": intent.finger_pairs,
                    "finger_width_um": intent.finger_width_um,
                    "gap_um": intent.gap_um,
                    "overlap_um": intent.overlap_um,
                }.items()
                if value is not None
            }
            optimization = optimize_idc(
                target_capacitance_pf=intent.target_capacitance_pf,
                frequency_ghz=intent.frequency_ghz,
                substrate_epsilon_r=intent.substrate_epsilon_r,
                min_width_um=intent.min_width_um,
                min_gap_um=intent.min_gap_um,
                initial_geometry=seed,
                tolerance_pct=analytical_tolerance_pct,
            )
            parameters = optimization.parameters
        spec = LayoutSpec(
            component="IDC",
            target={
                "capacitance_pf": intent.target_capacitance_pf,
                **({"frequency_ghz": intent.frequency_ghz} if intent.frequency_ghz else {}),
            },
            parameters=parameters,
            rules={"min_width_um": intent.min_width_um, "min_gap_um": intent.min_gap_um},
            outputs={"gds": True, "svg": True, "json": False, "png": False},
            metadata={
                "source": "deterministic_prompt_parser",
                "prompt": intent.prompt,
                "substrate": intent.substrate,
                "substrate_epsilon_r": intent.substrate_epsilon_r,
                "assumptions": list(intent.assumptions),
            },
        )
    else:
        spec = cpw_spec_from_intent(intent)
    return CompiledText(intent, spec, optimization)


def run_from_text(
    prompt: str,
    output_dir: str | Path,
    *,
    tolerance_pct: float = 5.0,
    analytical_tolerance_pct: float = 1.0,
    solver_executable: str | None = None,
) -> FromTextResult:
    """Compile text, size geometry, verify, prepare/execute extraction, report."""
    # Local import avoids a composition-root cycle through textlayout.__init__.
    from textlayout import build_default_workflow

    compiled = compile_text(prompt, analytical_tolerance_pct=analytical_tolerance_pct)
    intent, spec, optimization = compiled.intent, compiled.spec, compiled.optimization
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    intent_path = out / "intent.json"
    layout_path = out / "layout.json"
    intent_path.write_text(json.dumps(intent.to_dict(), indent=2) + "\n", encoding="utf-8")
    layout_path.write_text(
        json.dumps(spec.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )

    workflow = build_default_workflow()
    generated = workflow.run(spec, formats=("gds", "svg"), output_dir=out, stem="output")
    verification = generated.report.to_dict()
    if not generated.report.passed:
        simulation = _base_simulation(
            EvidenceStatus.FAILED,
            EvidenceStatus.FAILED,
            "Layout verification failed; solver preparation was not attempted.",
        )
    elif spec.component == "IDC":
        solver_tuning: list[dict[str, Any]] = []
        for solver_iteration in range(3):
            prepared = prepare_idc_fastercap(
                spec,
                generated.geometry,
                workflow.technology(spec.technology),
                out / "simulation" / f"iteration_{solver_iteration}",
            )
            executed = run_fastercap(
                prepared,
                executable=solver_executable,
                target_capacitance_pf=spec.target["capacitance_pf"],
                tolerance_pct=tolerance_pct,
            )
            comparison = executed.target_comparison or {}
            solver_tuning.append(
                {
                    "iteration": solver_iteration,
                    "parameters": dict(spec.parameters),
                    "solver_status": executed.status,
                    "comparison": comparison or None,
                }
            )
            if executed.status != "executed" or comparison.get("within_tolerance"):
                break
            extracted_pf = executed.extracted_quantities.get("mutual_capacitance_pf")
            if not isinstance(extracted_pf, (int, float)) or extracted_pf <= 0:
                break
            adjusted = dict(spec.parameters)
            adjusted["overlap_um"] = round(
                float(adjusted["overlap_um"])
                * float(spec.target["capacitance_pf"])
                / float(extracted_pf),
                3,
            )
            spec = spec.model_copy(update={"parameters": adjusted})
            layout_path.write_text(
                json.dumps(spec.model_dump(mode="json"), indent=2) + "\n",
                encoding="utf-8",
            )
            generated = workflow.run(
                spec, formats=("gds", "svg"), output_dir=out, stem="output"
            )
        verification = generated.report.to_dict()
        simulation = _solver_contract(executed, prepared, tolerance_pct)
        simulation["solver_tuning_iterations"] = solver_tuning
    else:
        simulation = _base_simulation(
            EvidenceStatus.ANALYTICAL_ONLY,
            EvidenceStatus.SKIPPED_SOLVER_ABSENT,
            "The first closed-loop benchmark executes capacitance extraction for IDC only.",
        )

    verification_path = out / "verification.json"
    simulation_path = out / "simulation.json"
    report_path = out / "report.md"
    verification_payload = {
        **verification,
        "analytical_optimization": None if optimization is None else optimization.to_dict(),
        "physics_verified": simulation["status"] == EvidenceStatus.PHYSICS_VERIFIED,
    }
    verification_path.write_text(
        json.dumps(verification_payload, indent=2) + "\n", encoding="utf-8"
    )
    simulation_path.write_text(json.dumps(simulation, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(
        _render_report(intent, spec, optimization, verification_payload, simulation),
        encoding="utf-8",
    )
    files = {
        "intent": str(intent_path),
        "layout": str(layout_path),
        "gds": str(out / "output.gds"),
        "svg": str(out / "output.svg"),
        "verification": str(verification_path),
        "simulation": str(simulation_path),
        "report": str(report_path),
    }
    return FromTextResult(intent, spec, files, verification_payload, simulation, optimization)


def _base_simulation(
    status: EvidenceStatus, solver_status: EvidenceStatus, reason: str
) -> dict[str, Any]:
    return {
        "schema": "textlayout.solver-evidence.v1",
        "status": status,
        "solver_status": solver_status,
        "reason": reason,
        "physics_verified": status == EvidenceStatus.PHYSICS_VERIFIED,
        "extracted_capacitance": None,
    }


def _solver_contract(result: Any, prepared: Any, tolerance_pct: float) -> dict[str, Any]:
    if result.status == "skipped":
        payload = _base_simulation(
            EvidenceStatus.SIMULATION_INPUT_PREPARED,
            EvidenceStatus.SKIPPED_SOLVER_ABSENT,
            result.reason,
        )
    elif result.status == "failed":
        payload = _base_simulation(EvidenceStatus.FAILED, EvidenceStatus.FAILED, result.reason)
    else:
        comparison = result.target_comparison or {}
        within = bool(comparison.get("within_tolerance"))
        status = EvidenceStatus.PHYSICS_VERIFIED if within else EvidenceStatus.SIMULATION_EXECUTED
        payload = _base_simulation(status, EvidenceStatus.SIMULATION_EXECUTED, result.reason)
        output_files = tuple(
            path
            for name, path in result.artifacts.items()
            if name in {"solver_stdout", "result"}
        )
        evidence = ExtractedValueEvidence.create(
            value=float(result.extracted_quantities["mutual_capacitance_pf"]),
            source=result.solver,
            command=tuple(result.command),
            input_files=tuple(prepared.artifacts.values()),
            output_files=output_files,
            parser_used="textlayout.simulation.fastercap._parse_capacitance_matrix_pf",
            units="pF",
            tolerance={
                "target": float(comparison["target"]),
                "tolerance_pct": tolerance_pct,
                "within_tolerance": within,
            },
        )
        payload["extracted_capacitance"] = evidence.to_dict()
        payload["comparison"] = comparison
    payload["input_files"] = list(prepared.artifacts.values())
    payload["solver_artifacts"] = dict(result.artifacts)
    return payload


def _render_report(
    intent: PromptIntent,
    spec: LayoutSpec,
    optimization: IDCOptimizationResult | None,
    verification: dict[str, Any],
    simulation: dict[str, Any],
) -> str:
    lines = [
        f"# Text-to-Layout {spec.component} Report",
        "",
        f"- Prompt: `{intent.prompt}`",
        f"- Component: `{spec.component}`",
        f"- Geometry verification: **{str(verification['status']).upper()}**",
        f"- Evidence status: **{simulation['status']}**",
    ]
    if optimization is not None:
        lines += [
            f"- Target capacitance: `{optimization.target_pf:.6g} pF`",
            f"- Bahl/Alley estimate: `{optimization.estimate_pf:.6g} pF`",
            f"- Analytical error: `{optimization.error_pct:.3f}%`",
            f"- Analytical iterations: `{len(optimization.iterations)}`",
        ]
    extracted = simulation.get("extracted_capacitance")
    if extracted:
        lines.append(f"- Extracted capacitance: `{extracted['value']:.6g} {extracted['units']}`")
    else:
        lines.append("- Extracted capacitance: `not available`")
    lines += ["", "## Solver evidence", "", simulation["reason"], ""]
    if simulation["status"] == EvidenceStatus.SIMULATION_INPUT_PREPARED:
        lines += [
            "The solver was skipped because no FasterCap/FastCap executable was found.",
            "Simulation input was prepared, but no physics verification was performed.",
            "",
        ]
    lines += [
        "## Limitations",
        "",
        "- The analytical Bahl/Alley model is a sizing estimate, not fabrication signoff.",
        "- The prepared solver model uses zero-thickness metal and an effective dielectric.",
        "- Fabrication readiness is not claimed.",
    ]
    return "\n".join(lines) + "\n"
