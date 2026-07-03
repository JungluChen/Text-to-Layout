"""Deterministic node implementations for the LangGraph layout workflow.

Every node is a small, pure-ish function ``state -> updates`` that delegates to
the deterministic stage helpers in :mod:`textlayout.workflows.from_text`. Nodes
never invent data: they only move the request through parse → size → DSL →
geometry → export → readback → solver → evidence → report.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textlayout.errors import PromptParseError
from textlayout.prompt import parse_prompt
from textlayout.verification.klayout_readback import read_back_gds, write_readback_json
from textlayout.workflow.state import MAX_SOLVER_ITERATIONS, LayoutWorkflowState
from textlayout.workflows.from_text import (
    _capacitance_result_payload,
    _render_jpa_report,
    _resonance_checked,
    _simulation_payload,
    _write_json,
    build_spec,
    run_circuit_checks,
    simulate_and_evidence,
    size_parameters,
)
from textlayout.workflows.generate import GenerateWorkflow


class PromptPipeline:
    """Node collection bound to one injected :class:`GenerateWorkflow`."""

    def __init__(self, generate_workflow: GenerateWorkflow) -> None:
        self._generate = generate_workflow

    # ------------------------------------------------------------------ #
    # 1. ParsePrompt
    def parse_prompt(self, state: LayoutWorkflowState) -> dict[str, Any]:
        out = Path(state.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        intent = parse_prompt(state.prompt)
        files = dict(state.files)
        files["intent"] = _write_json(out / "intent.json", intent.model_dump(mode="json"))
        return {"intent": intent, "files": files}

    # 2. ValidateIntent
    def validate_intent(self, state: LayoutWorkflowState) -> dict[str, Any]:
        intent = state.intent
        assert intent is not None
        layout_component = "IDC" if intent.component == "JPA" else intent.component
        known = self._generate.component_names
        if layout_component not in known:
            raise PromptParseError(
                intent.prompt,
                f"component {layout_component!r} has no registered generator",
                hints=[f"registered components: {known}"],
            )
        if intent.technology not in self._generate.technology_names:
            raise PromptParseError(
                intent.prompt,
                f"technology {intent.technology!r} is not registered",
                hints=[f"registered technologies: {self._generate.technology_names}"],
            )
        warnings = list(state.warnings)
        if not intent.target:
            warnings.append(
                "No numeric design target stated; defaults are used and no target "
                "comparison will be possible."
            )
        return {"warnings": warnings}

    # 3. BuildLayoutDSL (initial sizing → validated DSL)
    def build_layout_dsl(self, state: LayoutWorkflowState) -> dict[str, Any]:
        intent = state.intent
        assert intent is not None
        out = Path(state.output_dir)
        technology = self._generate.technology(intent.technology)
        sizing = size_parameters(intent, technology, tolerance_percent=state.tolerance_percent)
        files = dict(state.files)
        if sizing.jpa_sizing is not None:
            files["design_equations"] = _write_json(
                out / "design_equations.json", sizing.jpa_sizing
            )
        spec = build_spec(intent, sizing)
        files["layout"] = _write_json(out / "layout.json", spec.model_dump(mode="json"))
        return {
            "layout_dsl": spec,
            "sized_parameters": dict(sizing.parameters),
            "optimization": sizing.optimization,
            "circuit_requests": sizing.circuit_requests,
            "lc_inductance_nh": sizing.lc_inductance_nh,
            "target_capacitance_pf": sizing.target_capacitance_pf,
            "jpa_sizing": sizing.jpa_sizing,
            "files": files,
        }

    # 4. OptimizeParameters (persist the analytical optimization record)
    def optimize_parameters(self, state: LayoutWorkflowState) -> dict[str, Any]:
        intent = state.intent
        assert intent is not None
        out = Path(state.output_dir)
        files = dict(state.files)
        if state.optimization is not None:
            files["optimization"] = _write_json(
                out / "optimization.json", state.optimization.model_dump(mode="json")
            )
        else:
            files["optimization"] = _write_json(
                out / "optimization.json",
                {
                    "schema": "textlayout.analytical-sizing.v1",
                    "component": intent.component,
                    "method": "deterministic analytical sizing",
                    "target": dict(intent.target),
                    "final_parameters": dict(state.sized_parameters),
                    "solver_executed": False,
                },
            )
        return {"files": files}

    # 5. GenerateGeometry
    def generate_geometry(self, state: LayoutWorkflowState) -> dict[str, Any]:
        spec = state.layout_dsl
        assert spec is not None
        result = self._generate.run(spec, output_dir=Path(state.output_dir), stem="output")
        return {"generate": result, "geometry_status": result.report.status}

    # 6. ExportArtifacts
    def export_artifacts(self, state: LayoutWorkflowState) -> dict[str, Any]:
        result = state.generate
        assert result is not None
        files = dict(state.files)
        files.update({k: v for k, v in result.files.items() if k in {"gds", "svg", "png"}})
        warnings = list(state.warnings)
        if not result.report.passed:
            warnings.append(
                "Geometry verification failed; final geometry artifacts were not exported."
            )
        return {"files": files, "warnings": warnings}

    # 7. KLayoutReadback
    def klayout_readback(self, state: LayoutWorkflowState) -> dict[str, Any]:
        result = state.generate
        assert result is not None
        gds_path = state.files.get("gds")
        if gds_path is None:
            return {"readback": None}
        spec = state.layout_dsl
        assert spec is not None
        readback = read_back_gds(
            gds_path, result.geometry, self._generate.technology(spec.technology)
        )
        files = dict(state.files)
        files["klayout_readback"] = str(
            write_readback_json(readback, Path(state.output_dir) / "klayout_readback.json")
        )
        return {"readback": readback, "files": files}

    # 8. GeometryVerification
    def geometry_verification(self, state: LayoutWorkflowState) -> dict[str, Any]:
        result = state.generate
        assert result is not None
        out = Path(state.output_dir)
        verification = result.report.to_dict()
        if state.readback is not None:
            verification["klayout_readback"] = state.readback.to_dict()
        files = dict(state.files)
        files["verification"] = _write_json(out / "verification.json", verification)
        readback_ok = state.readback.passed if state.readback is not None else False
        geometry_status = "GEOMETRY_PASS" if result.report.passed and readback_ok else "FAILED"
        return {
            "verification_result": verification,
            "geometry_status": geometry_status,
            "files": files,
        }

    # 9. PrepareFasterCap (solver input generation, never execution)
    def prepare_fastercap(self, state: LayoutWorkflowState) -> dict[str, Any]:
        evidence, simulation = self._simulate(state, execute=False)
        return {"evidence": evidence, "simulation": simulation}

    # 10. RunFasterCapIfAvailable (guarded execution)
    def run_fastercap_if_available(self, state: LayoutWorkflowState) -> dict[str, Any]:
        if not state.execute_solver:
            return {}
        simulation = state.simulation
        if simulation is None or simulation.status != "input_files_prepared":
            return {}
        evidence, executed = self._simulate(state, execute=True)
        return {"evidence": evidence, "simulation": executed}

    # 11. ParseSolverResult
    def parse_solver_result(self, state: LayoutWorkflowState) -> dict[str, Any]:
        assert state.simulation is not None and state.evidence is not None
        out = Path(state.output_dir)
        payload = _capacitance_result_payload(state.simulation, state.evidence)
        files = dict(state.files)
        files["capacitance_result"] = _write_json(
            out / "extraction" / "capacitance_result.json", payload
        )
        return {"simulation_result": payload, "files": files}

    # 12. CompareTarget (records one solver-loop iteration and its verdict)
    def compare_target(self, state: LayoutWorkflowState) -> dict[str, Any]:
        assert state.evidence is not None
        updates: dict[str, Any] = {"evidence_status": state.evidence.status.value}
        if state.optimization is not None and state.target_capacitance_pf is not None:
            simulation = state.simulation
            assert simulation is not None and state.layout_dsl is not None
            generate = state.generate
            iterations = list(state.solver_iterations)
            iterations.append(
                {
                    "iteration": state.iteration + 1,
                    "parameters": dict(state.layout_dsl.parameters),
                    "solver_status": simulation.status,
                    "extracted_capacitance_pf": simulation.extracted_quantities.get(
                        "mutual_capacitance_pf"
                    ),
                    "target_comparison": simulation.target_comparison,
                    "verification_passed": bool(generate and generate.report.passed),
                }
            )
            updates["solver_iterations"] = iterations
            updates["iteration"] = state.iteration + 1
        return updates

    # 12b. RetuneParameters (only reached via the conditional edge)
    def retune_parameters(self, state: LayoutWorkflowState) -> dict[str, Any]:
        spec = state.layout_dsl
        simulation = state.simulation
        target_c = state.target_capacitance_pf
        assert spec is not None and simulation is not None and target_c is not None
        extracted = simulation.extracted_quantities.get("mutual_capacitance_pf")
        assert isinstance(extracted, (int, float)) and extracted > 0
        tuned = dict(spec.parameters)
        tuned["overlap_um"] = _retuned_overlap(float(tuned["overlap_um"]), target_c, extracted)
        new_spec = spec.model_copy(update={"parameters": tuned})
        files = dict(state.files)
        files["layout"] = _write_json(
            Path(state.output_dir) / "layout.json", new_spec.model_dump(mode="json")
        )
        return {"layout_dsl": new_spec, "files": files}

    # 13. RunCircuitChecks (JoSIM / PSCAN2 / WRspice when requested)
    def run_circuit_checks(self, state: LayoutWorkflowState) -> dict[str, Any]:
        intent = state.intent
        evidence = state.evidence
        assert intent is not None and evidence is not None
        out = Path(state.output_dir)
        circuit_sims = run_circuit_checks(
            intent,
            evidence,
            state.circuit_requests,
            out,
            target_c=state.target_capacitance_pf,
            lc_inductance_nh=state.lc_inductance_nh,
            execute_solver=state.execute_solver,
        )
        resonance_passed = any(_resonance_checked(sim) for sim in circuit_sims.values())
        circuit_failed = any(sim.status == "failed" for sim in circuit_sims.values())
        physics_verified = bool(
            evidence.is_physics_verified
            and not circuit_failed
            and (intent.component != "JPA" or resonance_passed)
        )
        updates: dict[str, Any] = {
            "circuit_simulations": circuit_sims,
            "physics_verified": physics_verified,
        }
        if state.optimization is not None and state.target_capacitance_pf is not None:
            simulation = state.simulation
            assert simulation is not None and state.layout_dsl is not None
            optimization = state.optimization.model_copy(
                update={
                    "solver_iterations": list(state.solver_iterations),
                    "final_parameters": dict(state.layout_dsl.parameters),
                    "final_basis": (
                        "solver_extracted" if simulation.status == "executed" else "analytical"
                    ),
                }
            )
            files = dict(state.files)
            files["optimization"] = _write_json(
                out / "optimization.json", optimization.model_dump(mode="json")
            )
            updates["optimization"] = optimization
            updates["files"] = files
        return updates

    # 14. GenerateReport
    def generate_report(self, state: LayoutWorkflowState) -> dict[str, Any]:
        intent, evidence, simulation = state.intent, state.evidence, state.simulation
        assert intent is not None and evidence is not None and simulation is not None
        assert state.layout_dsl is not None and state.generate is not None
        out = Path(state.output_dir)
        files = dict(state.files)
        payload = _simulation_payload(
            intent,
            evidence,
            simulation,
            state.circuit_simulations,
            lc_inductance_nh=state.lc_inductance_nh,
            jpa_sizing=state.jpa_sizing,
            physics_verified=state.physics_verified,
        )
        files["simulation"] = _write_json(out / "simulation" / "simulation.json", payload)
        files["simulation_legacy"] = _write_json(out / "simulation.json", payload)

        report_path = out / "report.md"
        report_path.write_text(
            _render_jpa_report(
                intent,
                state.layout_dsl,
                state.generate,
                state.optimization,
                evidence,
                state.circuit_simulations,
                files,
                jpa_sizing=state.jpa_sizing,
                physics_verified=state.physics_verified,
            ),
            encoding="utf-8",
        )
        files["report"] = str(report_path)
        return {"files": files}

    # 15. UpdateShowcaseMetadata
    def update_showcase_metadata(self, state: LayoutWorkflowState) -> dict[str, Any]:
        artifacts = {kind: str(Path(path)) for kind, path in state.files.items()}
        return {"artifacts": artifacts}

    # ------------------------------------------------------------------ #
    def _simulate(self, state: LayoutWorkflowState, *, execute: bool) -> tuple[Any, Any]:
        intent = state.intent
        assert intent is not None and state.layout_dsl is not None and state.generate is not None
        return simulate_and_evidence(
            self._generate,
            intent,
            state.layout_dsl,
            state.generate,
            Path(state.output_dir),
            tolerance_percent=state.tolerance_percent,
            execute_solver=execute,
            solver_executable=state.solver_executable,
        )


def should_retune(state: LayoutWorkflowState) -> bool:
    """Pure decision function for the CompareTarget → GenerateGeometry cycle.

    Mirrors the pre-graph loop conditions exactly: retune only while a real
    solver executed, extracted a positive value that misses tolerance, the
    overlap knob still moves, and the iteration budget remains.
    """
    if state.optimization is None or state.target_capacitance_pf is None:
        return False
    if state.iteration >= MAX_SOLVER_ITERATIONS:
        return False
    simulation = state.simulation
    if simulation is None or simulation.status != "executed":
        return False
    extracted = simulation.extracted_quantities.get("mutual_capacitance_pf")
    if not isinstance(extracted, (int, float)) or extracted <= 0:
        return False
    comparison = simulation.target_comparison
    if comparison is not None and comparison.get("within_tolerance"):
        return False
    spec = state.layout_dsl
    if spec is None or "overlap_um" not in spec.parameters:
        return False
    current = float(spec.parameters["overlap_um"])
    return _retuned_overlap(current, state.target_capacitance_pf, float(extracted)) != current


def _retuned_overlap(current_um: float, target_pf: float, extracted_pf: float) -> float:
    return round(max(20.0, min(2000.0, current_um * target_pf / extracted_pf)), 4)


def summarize_state(state: LayoutWorkflowState) -> dict[str, Any]:
    """Compact JSON-safe view used by the trace's input/output summaries."""
    return {
        "component": state.intent.component if state.intent else None,
        "geometry_status": state.geometry_status,
        "evidence_status": state.evidence_status,
        "iteration": state.iteration,
        "files": sorted(state.files),
    }


def json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)
