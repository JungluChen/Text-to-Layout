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
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from textlayout.evidence import EvidenceStatus, QuantityEvidence
from textlayout.optimization import IDCOptimizationResult, optimize_idc
from textlayout.prompt import DesignIntent
from textlayout.research import formulas as F
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation import (
    SimulationResult,
    prepare_idc_josim,
    prepare_idc_pscan2,
    prepare_idc_wrspice,
    run_idc_josim,
    run_idc_pscan2,
    run_idc_wrspice,
    simulate_layout,
)
from textlayout.simulation.evidence_map import capacitance_evidence, quantity_evidence
from textlayout.workflows.generate import GenerateResult, GenerateWorkflow

FROM_TEXT_SCHEMA = "textlayout.from-text.v1"

_ANALYTICAL_MODEL_IDC = "Bahl/Alley quasi-static closed form (Bahl 2003, Alley 1970)"
_PHI0_WB = 2.067833848e-15


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
    circuit_simulations: dict[str, SimulationResult] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.generate.report.passed

    @property
    def missing_circuit_simulators(self) -> list[str]:
        """Requested circuit backends whose executable/module was absent."""
        return [name for name, sim in self.circuit_simulations.items() if sim.status == "skipped"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": FROM_TEXT_SCHEMA,
            "status": "ok" if self.ok else "verification_failed",
            "component": self.intent.component,
            "layout_component": self.spec.component,
            "target": dict(self.spec.target),
            "simulation_status": self.evidence.status.value,
            "simulation_summary": self.evidence.summary_line(),
            "circuit_simulators": {
                name: {"status": sim.status, "evidence_level": sim.evidence_level}
                for name, sim in self.circuit_simulations.items()
            },
            "artifacts": {name: Path(p).name for name, p in self.files.items()},
            "output_dir": str(self.output_dir),
        }


@dataclass(slots=True)
class SizingOutcome:
    """Everything the deterministic sizing stage decides for one request."""

    parameters: dict[str, Any]
    optimization: IDCOptimizationResult | None
    circuit_requests: dict[str, tuple[bool, bool]]
    lc_inductance_nh: Any
    target_capacitance_pf: float | None
    jpa_sizing: dict[str, Any] | None


#: Sub-device parameter names shared between IDCSpec and TestStructureSpec.
_IDC_PARAM_KEYS = ("finger_pairs", "finger_width_um", "gap_um", "overlap_um", "bus_width_um")


def size_parameters(
    intent: DesignIntent,
    technology: Any,
    *,
    tolerance_percent: float,
) -> SizingOutcome:
    """Deterministic analytical sizing: intent → generator parameters."""
    optimization: IDCOptimizationResult | None = None
    parameters: dict[str, Any] = dict(intent.parameters)
    circuit_requests = {
        name: (
            bool(parameters.pop(f"{name}_check", False)),
            bool(parameters.pop(f"{name}_jj_check", False)),
        )
        for name in ("josim", "pscan2", "wrspice")
    }
    jpa_sizing = _jpa_design_equations(intent) if intent.component == "JPA" else None
    lc_inductance_nh = parameters.pop("lc_inductance_nh", None)
    if jpa_sizing is not None:
        lc_inductance_nh = jpa_sizing["assumptions"]["selected_inductance_nh"]
    target_c = (
        float(jpa_sizing["results"]["required_capacitance_pf"])
        if jpa_sizing is not None
        else intent.target.get("capacitance_pf")
    )
    if intent.component in {"IDC", "JPA", "TestStructure"} and target_c is not None:
        optimization = optimize_idc(
            target_capacitance_pf=target_c,
            substrate_epsilon_r=technology.substrate_epsilon_r,
            min_finger_width_um=intent.constraints.get(
                "min_width_um", technology.min_width_for("M1")
            ),
            min_gap_um=intent.constraints.get("min_gap_um", technology.min_spacing_for("M1")),
            initial_parameters=(
                {k: v for k, v in intent.parameters.items() if k in _IDC_PARAM_KEYS}
                if intent.component in {"IDC", "TestStructure"}
                else {}
            ),
            tolerance_percent=tolerance_percent,
        )
        parameters = dict(optimization.final_parameters)
        if intent.component == "JPA":
            parameters.update(
                {
                    "squid_placeholder_enabled": True,
                    "squid_placeholder_width_um": 40.0,
                    "squid_placeholder_height_um": 30.0,
                    "squid_placeholder_clearance_um": 20.0,
                    "squid_placeholder_layer": "JJ",
                }
            )
        elif intent.component == "TestStructure":
            parameters = _test_structure_parameters(intent, parameters, technology)
    elif intent.component == "IDC":
        parameters = {
            "finger_pairs": 10,
            "finger_width_um": 4.0,
            "gap_um": 2.0,
            "overlap_um": 250.0,
            "bus_width_um": 25.0,
            **parameters,
        }
    elif intent.component == "TestStructure":
        parameters = _test_structure_parameters(intent, parameters, technology)
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
        width = float(parameters.get("trace_width_um", 5.0))
        spacing = float(parameters.get("spacing_um", 3.0))
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
    elif intent.component == "TestChip":
        parameters = _test_chip_parameters(intent, parameters, technology)
    return SizingOutcome(
        parameters=parameters,
        optimization=optimization,
        circuit_requests=circuit_requests,
        lc_inductance_nh=lc_inductance_nh,
        target_capacitance_pf=target_c,
        jpa_sizing=jpa_sizing,
    )


def _test_structure_parameters(
    intent: DesignIntent, idc_parameters: dict[str, Any], technology: Any
) -> dict[str, Any]:
    feed_width = 10.0
    target_z0 = intent.target.get("impedance_ohm", 50.0)
    parameters: dict[str, Any] = {
        "finger_pairs": 20,
        "finger_width_um": 4.0,
        "gap_um": 2.0,
        "overlap_um": 250.0,
        "bus_width_um": 25.0,
        **{k: v for k, v in idc_parameters.items() if k in _IDC_PARAM_KEYS},
        "feed_width_um": feed_width,
        "feed_gap_um": round(
            F.cpw_gap_for_z0(target_z0, feed_width, technology.substrate_epsilon_r), 4
        ),
    }
    return parameters


def _test_chip_parameters(
    intent: DesignIntent, parsed: dict[str, Any], technology: Any
) -> dict[str, Any]:
    eps_r = technology.substrate_epsilon_r
    cpw_width = 10.0
    target_z0 = intent.target.get("impedance_ohm", 50.0)
    target_c = intent.target.get("capacitance_pf", 0.6)
    target_nh = intent.target.get("inductance_nh", 3.0)
    turns = int(parsed.get("spiral_turns", 4))
    trace, spacing = 4.0, 2.0
    outer = _spiral_outer_for_target(turns, trace, spacing, target_nh)
    parameters: dict[str, Any] = {
        "idc_finger_pairs": F.idc_finger_pairs_for_target(target_c, 250.0, eps_r),
        "cpw_center_width_um": cpw_width,
        "cpw_gap_um": round(F.cpw_gap_for_z0(target_z0, cpw_width, eps_r), 4),
        "spiral_turns": turns,
        "spiral_outer_dimension_um": round(outer, 4),
        "spiral_trace_width_um": trace,
        "spiral_spacing_um": spacing,
    }
    for key in ("tile_width_um", "tile_height_um", "idc_finger_width_um", "idc_gap_um", "title"):
        if key in parsed:
            parameters[key] = parsed[key]
    return parameters


def build_spec(intent: DesignIntent, sizing: SizingOutcome) -> LayoutSpec:
    """Assemble the validated Layout DSL for the sized request."""
    layout_target = dict(intent.target)
    if sizing.target_capacitance_pf is not None:
        layout_target["capacitance_pf"] = float(sizing.target_capacitance_pf)
    return LayoutSpec(
        component="IDC" if intent.component == "JPA" else intent.component,
        technology=intent.technology,
        target=layout_target,
        parameters=sizing.parameters,
        rules=dict(intent.constraints),
        outputs={"gds": True, "svg": True, "png": True, "json": False},
        metadata={
            "prompt": intent.prompt,
            "intent_schema": intent.schema_version,
            "josim_check_requested": sizing.circuit_requests["josim"][0],
            "josim_jj_check_requested": sizing.circuit_requests["josim"][1],
            "pscan2_check_requested": sizing.circuit_requests["pscan2"][0],
            "wrspice_check_requested": sizing.circuit_requests["wrspice"][0],
            "lc_inductance_nh": sizing.lc_inductance_nh,
            "design_component": intent.component,
            "topology": intent.topology,
            "capacitor_type": intent.capacitor_type,
            "gain_target_db": intent.target.get("gain_db"),
            "bandwidth_mhz": intent.target.get("bandwidth_mhz"),
        },
    )


class FromTextWorkflow:
    """Drives the prompt → artifacts loop on top of a :class:`GenerateWorkflow`.

    Since the LangGraph upgrade this class is a thin façade: :meth:`run`
    executes the staged pipeline in ``textlayout.workflow.graph`` (ParsePrompt →
    … → UpdateShowcaseMetadata) and returns the same :class:`FromTextResult`
    contract as before. The deterministic stage logic lives in this module; the
    graph owns only orchestration, tracing, and the solver retune loop.
    """

    def __init__(self, generate_workflow: GenerateWorkflow) -> None:
        self._generate = generate_workflow

    @property
    def generate_workflow(self) -> GenerateWorkflow:
        return self._generate

    def run(
        self,
        prompt: str,
        output_dir: str | Path,
        *,
        tolerance_percent: float = 5.0,
        execute_solver: bool = True,
        solver_executable: str | None = None,
    ) -> FromTextResult:
        from textlayout.workflow.graph import run_prompt_workflow

        return run_prompt_workflow(
            self._generate,
            prompt,
            output_dir,
            tolerance_percent=tolerance_percent,
            execute_solver=execute_solver,
            solver_executable=solver_executable,
        )


def run_circuit_checks(
    intent: DesignIntent,
    evidence: QuantityEvidence,
    circuit_requests: Mapping[str, tuple[bool, bool]],
    out: Path,
    *,
    target_c: float | None,
    lc_inductance_nh: Any,
    execute_solver: bool,
) -> dict[str, SimulationResult]:
    """Prepare (and, when allowed, execute) each requested circuit backend.

    Circuit simulators consume the best available capacitance value but can
    never improve its provenance — the ``capacitance_source`` string rides
    along into every generated deck and manifest.
    """
    if intent.component not in {"IDC", "JPA"} or not any(
        flag for flag, _ in circuit_requests.values()
    ):
        return {}
    capacitance_value = evidence.extracted_value or evidence.analytical_value or target_c
    if capacitance_value is None:
        return {}
    capacitance_source = (
        "FasterCap/FastCap extracted value"
        if evidence.extracted_value is not None
        else "analytical estimate (not geometry-extracted)"
    )
    backends: dict[str, tuple[Any, Any]] = {
        "josim": (prepare_idc_josim, run_idc_josim),
        "pscan2": (prepare_idc_pscan2, run_idc_pscan2),
        "wrspice": (prepare_idc_wrspice, run_idc_wrspice),
    }
    inductance = float(lc_inductance_nh) if isinstance(lc_inductance_nh, (int, float)) else None
    results: dict[str, SimulationResult] = {}
    for name, (requested, jj_requested) in circuit_requests.items():
        if not requested:
            continue
        prepare_fn, run_fn = backends[name]
        prepared: SimulationResult = prepare_fn(
            out / "simulation" / name,
            capacitance_pf=float(capacitance_value),
            capacitance_source=capacitance_source,
            target_frequency_ghz=intent.target.get("frequency_ghz"),
            stray_inductance_nh=inductance,
            include_jj=jj_requested,
        )
        results[name] = run_fn(prepared) if execute_solver else prepared
    return results


def simulate_and_evidence(
    generate_workflow: GenerateWorkflow,
    intent: DesignIntent,
    spec: LayoutSpec,
    result: GenerateResult,
    out: Path,
    *,
    tolerance_percent: float,
    execute_solver: bool,
    solver_executable: str | None,
) -> tuple[QuantityEvidence, SimulationResult]:
    """Guarded solver stage: prepare inputs, execute when allowed, map to evidence."""
    target_c = spec.target.get("capacitance_pf")
    analytical = result.research.analytical_estimates.get("estimated_capacitance_pf")
    analytical_value = float(analytical) if isinstance(analytical, (int, float)) else None

    if not result.report.passed:
        failed = QuantityEvidence(
            quantity="capacitance",
            target_value=target_c,
            target_unit="pF" if target_c is not None else None,
            analytical_value=analytical_value,
            analytical_model=_ANALYTICAL_MODEL_IDC if analytical_value is not None else None,
            tolerance_percent=tolerance_percent,
            status=EvidenceStatus.FAILED,
            notes=["Geometry verification failed; simulation was not attempted."],
        )
        return failed, SimulationResult(
            status="failed",
            solver="FasterCap/FastCap",
            readiness_level=1,
            reason="Geometry verification failed.",
            output_dir=out / "extraction" / "capacitance_input",
        )

    if intent.component == "TestChip":
        # Multi-device tile: no single solver models the assembled tile; every
        # electrical number stays a per-sub-device analytical estimate.
        tile_evidence = QuantityEvidence(
            quantity="geometry",
            tolerance_percent=tolerance_percent,
            status=EvidenceStatus.ANALYTICAL_ONLY,
            analytical_model="per-sub-device analytical estimates (see research report)",
            notes=[
                "TestChip is a geometry-level comparison tile; sub-device estimates are "
                "analytical and no solver was executed on the assembled tile.",
                "The IDC sub-block geometry is identical to the standalone IDC and can be "
                "extracted separately with FasterCap.",
            ],
        )
        return tile_evidence, SimulationResult(
            status="planned",
            solver="none",
            readiness_level=1,
            reason="No tile-level solver is registered; sub-blocks are geometry-only here.",
            output_dir=out / "extraction" / "capacitance_input",
        )

    cap_root = out / "extraction"
    cap_input = cap_root / "capacitance_input"
    cap_root.mkdir(parents=True, exist_ok=True)
    simulation = simulate_layout(
        spec,
        result.geometry,
        generate_workflow.technology(spec.technology),
        cap_input,
        solver="auto",
        execute=execute_solver,
        executable=solver_executable,
        tolerance_pct=tolerance_percent,
    )
    if spec.component in {"IDC", "TestStructure"}:
        return capacitance_evidence(
            simulation,
            target_capacitance_pf=target_c,
            tolerance_percent=tolerance_percent,
            analytical_value_pf=analytical_value,
            analytical_model=_ANALYTICAL_MODEL_IDC,
        ), simulation
    evidence_config = {
        "CPW": (
            "characteristic_impedance",
            "characteristic_impedance_ohm",
            "ohm",
            intent.target.get("impedance_ohm"),
            "estimated_z0_ohm",
            "textlayout.simulation.runners.extract_cpw_from_touchstone",
        ),
        "SpiralInductor": (
            "inductance",
            "inductance_nh",
            "nH",
            intent.target.get("inductance_nh"),
            "estimated_inductance_nh",
            "textlayout.simulation.runners.parse_fasthenry_inductance",
        ),
        "QuarterWaveResonator": (
            "resonance_frequency",
            "resonance_frequency_ghz",
            "GHz",
            intent.target.get("frequency_ghz"),
            "target_frequency_ghz",
            "textlayout.simulation.runners.extract_resonance_from_touchstone",
        ),
        "SQUID": (
            "mean_voltage",
            "mean_voltage_uv",
            "uV",
            intent.target.get("voltage_uv"),
            "josephson_inductance_ph_per_junction",
            "textlayout.simulation.josim.parse_josim_csv",
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
    ), simulation


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return str(path)


def _jpa_design_equations(intent: DesignIntent) -> dict[str, Any]:
    frequency_ghz = float(intent.target["frequency_ghz"])
    bandwidth_mhz = float(intent.target["bandwidth_mhz"])
    assumption = intent.inductance_assumption or {}
    inductance_nh = float(assumption.get("value_nh", 3.0))
    frequency_hz = frequency_ghz * 1e9
    bandwidth_hz = bandwidth_mhz * 1e6
    inductance_h = inductance_nh * 1e-9
    capacitance_f = 1.0 / ((2.0 * math.pi * frequency_hz) ** 2 * inductance_h)
    loaded_q = frequency_hz / bandwidth_hz
    critical_current_a = _PHI0_WB / (2.0 * math.pi * inductance_h)
    flux_fraction = 0.25
    tuned_inductance_h = inductance_h / abs(math.cos(math.pi * flux_fraction))
    tuned_frequency_hz = 1.0 / (2.0 * math.pi * math.sqrt(tuned_inductance_h * capacitance_f))
    warnings = [
        "The SQUID-equivalent inductance is an assumed small-signal value, not extracted layout evidence.",
        "The calculated IDC capacitance is an analytical target until an electrostatic solver runs.",
        "The gain target is recorded but nonlinear pump/signal/idler gain simulation is not implemented.",
    ]
    if not bool(assumption.get("user_provided")):
        warnings.insert(0, "The user did not provide inductance; the MVP assumes 3.0 nH.")
    return {
        "schema": "textlayout.jpa-design-equations.v1",
        "evidence_status": "DESIGN_SIZED_ANALYTICALLY",
        "constants": {"Phi0_Wb": _PHI0_WB},
        "equations": {
            "lc_resonance": "f0 = 1 / (2*pi*sqrt(L*C))",
            "required_capacitance": "C = 1 / ((2*pi*f0)^2 * L)",
            "loaded_q": "Q_loaded = f0 / BW",
            "josephson_inductance": "LJ0 = Phi0 / (2*pi*Ic)",
            "squid_tunability": "LJ(phi) = LJ0 / abs(cos(pi*phi/Phi0))",
        },
        "inputs": {
            "target_frequency_ghz": frequency_ghz,
            "bandwidth_mhz": bandwidth_mhz,
            "gain_target_db": intent.target.get("gain_db"),
        },
        "assumptions": {
            "selected_inductance_nh": inductance_nh,
            "inductance_source": assumption.get("source", "workflow_default"),
            "squid_model": "ideal symmetric SQUID, negligible loop inductance, small signal",
            "tunability_evaluation_flux_over_Phi0": flux_fraction,
            "stray_inductance_nh": 0.0,
        },
        "results": {
            "required_capacitance_f": capacitance_f,
            "required_capacitance_pf": capacitance_f * 1e12,
            "loaded_q": loaded_q,
            "assumed_effective_critical_current_a": critical_current_a,
            "assumed_effective_critical_current_ua": critical_current_a * 1e6,
            "LJ0_h": inductance_h,
            "LJ_at_0p25_Phi0_h": tuned_inductance_h,
            "frequency_at_0p25_Phi0_ghz": tuned_frequency_hz / 1e9,
        },
        "warnings": warnings,
    }


def _capacitance_status_label(simulation: SimulationResult) -> str:
    if simulation.status == "skipped":
        return "SKIPPED_SOLVER_ABSENT"
    if simulation.status == "failed":
        return "FAILED"
    if simulation.status == "executed" and simulation.extracted_quantities:
        return "CAPACITANCE_EXTRACTED"
    return "EXTRACTION_INPUT_PREPARED"


def _capacitance_result_payload(
    simulation: SimulationResult, evidence: QuantityEvidence
) -> dict[str, Any]:
    return {
        "schema": "textlayout.capacitance-extraction-result.v1",
        "status": _capacitance_status_label(simulation),
        "backend_status": simulation.status,
        "solver": simulation.solver,
        "solver_version": simulation.solver_version,
        "command": list(simulation.command),
        "return_code": simulation.return_code,
        "runtime_seconds": simulation.runtime_seconds,
        "artifacts": dict(simulation.artifacts),
        "extracted_quantities": dict(simulation.extracted_quantities),
        "target_comparison": simulation.target_comparison,
        "analytical_capacitance_pf": evidence.analytical_value,
        "reason": simulation.reason,
        "warnings": list(simulation.warnings),
    }


def _simulation_payload(
    intent: DesignIntent,
    evidence: QuantityEvidence,
    capacitance_simulation: SimulationResult,
    circuit_sims: Mapping[str, SimulationResult],
    *,
    lc_inductance_nh: Any,
    jpa_sizing: dict[str, Any] | None,
    physics_verified: bool,
) -> dict[str, Any]:
    capacitance_source = (
        "geometry_extracted"
        if evidence.extracted_value is not None
        else "analytical_estimate_not_geometry_extracted"
    )
    inductance_source = (
        (intent.inductance_assumption or {}).get("source", "unspecified")
        if intent.component == "JPA"
        else "prompt_or_workflow_default"
    )
    analytical_f0 = (
        float(jpa_sizing["inputs"]["target_frequency_ghz"])
        if jpa_sizing is not None
        else intent.target.get("frequency_ghz")
    )
    evidence_record = json.loads(evidence.model_dump_json())
    if intent.component == "JPA" and not physics_verified:
        if evidence_record.get("status") == "PHYSICS_VERIFIED":
            evidence_record["status"] = "CAPACITANCE_EXTRACTED"
            evidence_record.setdefault("notes", []).append(
                "Capacitance extraction alone does not verify the complete JPA workflow."
            )
    return {
        "schema": "textlayout.simulation-evidence.v1",
        "status": (
            "PHYSICS_VERIFIED"
            if physics_verified
            else "NOT_VERIFIED"
            if intent.component == "JPA"
            else evidence.status.value
        ),
        "solver": capacitance_simulation.solver,
        "solver_executed": capacitance_simulation.solver_executed,
        "capacitance_matrix_parsed": capacitance_simulation.capacitance_matrix_parsed,
        "target_compared": capacitance_simulation.target_compared,
        "mutual_capacitance_pf": capacitance_simulation.extracted_quantities.get(
            "mutual_capacitance_pf"
        ),
        "capacitance_matrix_pf": capacitance_simulation.extracted_quantities.get(
            "capacitance_matrix_pf"
        ),
        "target_comparison": capacitance_simulation.target_comparison,
        "artifacts": dict(capacitance_simulation.artifacts),
        "capacitance_source": capacitance_source,
        "capacitance_pf": evidence.extracted_value or evidence.analytical_value,
        "capacitance_extraction_status": _capacitance_status_label(capacitance_simulation),
        "inductance_source": inductance_source,
        "inductance_nh": lc_inductance_nh,
        "analytical_f0_ghz": analytical_f0,
        "gain_target_db": intent.target.get("gain_db"),
        "gain_status": "NOT_SUPPORTED_MVP",
        "evidence": [evidence_record],
        "backends": {
            name: (circuit_sims[name].to_dict() if name in circuit_sims else None)
            for name in ("josim", "pscan2", "wrspice")
        },
        "physics_verified": physics_verified,
    }


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


def _resonance_checked(sim: SimulationResult) -> bool:
    """True only for an executed run whose resonance met the LC expectation."""
    return bool(
        sim.evidence_level is not None
        and sim.evidence_level.endswith("_RESONANCE_CHECKED")
        and sim.target_comparison is not None
        and sim.target_comparison.get("within_tolerance")
    )


def _render_report(
    intent: DesignIntent,
    spec: LayoutSpec,
    result: GenerateResult,
    optimization: IDCOptimizationResult | None,
    evidence: QuantityEvidence,
    circuit_sims: dict[str, SimulationResult],
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
    analytical = f"{evidence.analytical_value}" if evidence.analytical_value is not None else "—"
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

    lines += ["## Circuit-simulator evidence (JoSIM / PSCAN2 / WRspice)", ""]
    if not circuit_sims:
        lines.append("- No circuit-level check was requested.")
    else:
        display = {"josim": "JoSIM", "pscan2": "PSCAN2", "wrspice": "WRspice"}
        lines += [
            "| Simulator | Evidence level | Executed | Result |",
            "| - | - | - | - |",
        ]
        for name, sim in circuit_sims.items():
            lines.append(
                f"| {display.get(name, name)} | **{sim.evidence_level}** "
                f"| {sim.solver_executed} | {sim.reason} |"
            )
        lines += [
            "",
            "- Circuit simulators validate transient LC/JJ behaviour only; they are "
            "never evidence that the physical IDC geometry has the target capacitance.",
            "- No parametric gain is claimed.",
        ]
    lines.append("")

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
            "- The optimizer uses the analytical model only; it never claims physics verification.",
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


def _capacitance_status_label_from_evidence(evidence: QuantityEvidence) -> str:
    if evidence.status is EvidenceStatus.SKIPPED_SOLVER_ABSENT:
        return "SKIPPED_SOLVER_ABSENT"
    if evidence.status is EvidenceStatus.SIMULATION_INPUT_PREPARED:
        return "EXTRACTION_INPUT_PREPARED"
    if evidence.status is EvidenceStatus.FAILED:
        return "FAILED"
    if evidence.status is EvidenceStatus.PHYSICS_VERIFIED:
        return "PHYSICS_VERIFIED"
    if evidence.status is EvidenceStatus.SIMULATION_EXECUTED:
        return "SIMULATION_EXECUTED"
    return "ANALYTICAL_ONLY"


def _render_jpa_report(
    intent: DesignIntent,
    spec: LayoutSpec,
    result: GenerateResult,
    optimization: IDCOptimizationResult | None,
    evidence: QuantityEvidence,
    circuit_sims: dict[str, SimulationResult],
    files: dict[str, str],
    *,
    jpa_sizing: dict[str, Any] | None,
    physics_verified: bool,
) -> str:
    geometry_pass = result.report.passed
    is_jpa = intent.component == "JPA"
    cap_label = _capacitance_status_label_from_evidence(evidence)
    overall_status = "PHYSICS_VERIFIED" if physics_verified else "NOT VERIFIED"
    lines = [
        f"# Text-to-Layout Report - {intent.component}",
        "",
        "## User requirement",
        "",
        f"`{intent.prompt}`",
        "",
        "## Parsed intent",
        "",
        f"- Component: `{intent.component}`",
        f"- Topology: `{intent.topology or spec.component}`",
        f"- Target frequency: `{intent.target.get('frequency_ghz')} GHz`",
        f"- Bandwidth: `{intent.target.get('bandwidth_mhz')} MHz`",
        f"- Gain target: `{intent.target.get('gain_db')} dB`",
        f"- Capacitor type: `{intent.capacitor_type or spec.component}`",
        f"- Requested simulators: `{', '.join(intent.simulator_requests) or 'none'}`",
        "",
        "## First-principles sizing",
        "",
    ]
    if jpa_sizing is not None:
        sizing_results = jpa_sizing["results"]
        lines += [
            "- Assumed SQUID-equivalent inductance: "
            f"`{jpa_sizing['assumptions']['selected_inductance_nh']} nH`",
            f"- Required capacitance: `{sizing_results['required_capacitance_pf']:.6g} pF`",
            f"- Loaded Q: `{sizing_results['loaded_q']:.6g}`",
            "- Implied effective critical current: "
            f"`{sizing_results['assumed_effective_critical_current_ua']:.6g} uA`",
            "- These values are analytical design inputs, not solver evidence.",
        ]
        lines += [f"- Warning: {warning}" for warning in jpa_sizing["warnings"]]
    else:
        lines.append("- See `optimization.json` and the analytical estimate artifacts.")
    placeholder = result.geometry.metadata.get("squid_placeholder", {})
    placeholder_status = (
        placeholder.get("physical_status", "not requested")
        if isinstance(placeholder, dict)
        else "not requested"
    )
    lines += [
        "",
        "## Generated layout",
        "",
        f"- Layout DSL component: `{spec.component}`",
        f"- Geometry role: `{result.geometry.metadata.get('layout_role', spec.component)}`",
        f"- Polygons: `{len(result.geometry.polygons)}`",
        f"- Ports: `{', '.join(port.name for port in result.geometry.ports)}`",
        f"- SQUID-equivalent placeholder: `{placeholder_status}`",
        "",
        "## Verification results",
        "",
        f"- Geometry verification: **{'PASS' if geometry_pass else 'FAIL'}**",
    ]
    for check in result.report.checks:
        suffix = f": {check.message}" if check.message else ""
        lines.append(f"- `{check.status.value.upper()}` {check.name}{suffix}")

    lines += [
        "",
        "## Extraction status",
        "",
        f"- Status: **{cap_label}**",
        f"- Simulation status: **{cap_label}**",
        "- Prepared FasterCap files: **yes**",
        "- Solver executed: "
        f"**{'yes' if evidence.extracted_value is not None else 'attempted' if evidence.command else 'no'}**",
        f"- Physics verified: **{'yes' if evidence.is_physics_verified else 'no'}**",
        f"- Evidence status: **{evidence.status.value}**",
        f"- {evidence.summary_line()}",
        f"- Analytical capacitance: `{evidence.analytical_value} pF`",
        "- Solver-extracted capacitance: "
        f"`{evidence.extracted_value if evidence.extracted_value is not None else 'not available'}`",
        "- Circuit simulators are not capacitance-extraction evidence.",
        "",
    ]
    if evidence.extracted_value is not None:
        lines += [
            f"- Extracted mutual capacitance: `{evidence.extracted_value:.6g} pF`",
            f"- Target capacitance: `{evidence.target_value:.6g} pF`"
            if evidence.target_value is not None
            else "- Target capacitance: `not provided`",
            f"- Error: `{((evidence.extracted_value - evidence.target_value) / evidence.target_value * 100):+.2f}%`"
            if evidence.target_value
            else "- Error: `not compared`",
            f"- Tolerance: `+/-{evidence.tolerance_percent:.2f}%`",
            "- Reason: extracted value is within tolerance."
            if evidence.is_physics_verified
            else "- Reason: extracted value is outside tolerance.",
            "",
        ]
    elif evidence.status is EvidenceStatus.SKIPPED_SOLVER_ABSENT:
        lines += ["- Reason: FasterCap/FastCap executable not found.", ""]
    elif evidence.status is EvidenceStatus.FAILED:
        lines += [
            "- Reason: solver failed or parser could not extract capacitance matrix.",
            "",
        ]
    if not is_jpa:
        lines += [
            f"- Legacy simulation status: **{evidence.status.value}**",
            f"- {_STATUS_EXPLANATIONS[evidence.status]}",
            "",
        ]

    display = {"josim": "JoSIM", "pscan2": "PSCAN2", "wrspice": "WRspice"}
    for name in ("josim", "pscan2", "wrspice"):
        lines += [f"## {display[name]} status", ""]
        sim = circuit_sims.get(name)
        if sim is None:
            lines.append("- Not requested.")
        else:
            lines += [
                f"- Evidence label: **{sim.evidence_level or 'INPUT_PREPARED'}**",
                f"- Executed: **{sim.solver_executed}**",
                f"- Result: {sim.reason}",
                f"- Command: `{list(sim.command) if sim.command else 'not executed'}`",
            ]
        lines.append("")

    if optimization is not None:
        lines += [
            "## Closed-loop analytical tuning",
            "",
            f"- Converged: **{optimization.converged}**",
            f"- Final parameters: `{json.dumps(optimization.final_parameters)}`",
            "- This optimizer is analytical unless extraction iterations are recorded.",
            "",
        ]

    lines += [
        "## What is verified",
        "",
        f"- Overall status: **{overall_status}**",
        f"- Deterministic layout and geometry checks: **{'verified' if geometry_pass else 'failed'}**",
    ]
    if evidence.extracted_value is not None:
        lines.append("- Geometry-level capacitance output was parsed from an executed solver.")
    if any(_resonance_checked(sim) for sim in circuit_sims.values()):
        lines.append("- At least one circuit-level resonance result passed its tolerance.")

    prepared = [display[name] for name, sim in circuit_sims.items() if not sim.solver_executed]
    lines += [
        "",
        "## What is only prepared",
        "",
        f"- Circuit backends without executed evidence: `{', '.join(prepared) or 'none'}`",
    ]
    if evidence.extracted_value is None:
        lines.append("- Capacitance extraction input exists, but no solver result exists.")

    lines += [
        "",
        "## Not yet supported",
        "",
        "- Full nonlinear pumped JPA gain, saturation, noise, and signal-idler verification.",
        "- Foundry-qualified Josephson-junction geometry and process DRC.",
        "- Gain is not checked because real pump, signal, and idler data are absent.",
        "",
        "## Artifacts",
        "",
    ]
    for kind, filename in sorted(files.items()):
        lines.append(f"- `{kind}`: `{filename}`")
    lines += [
        "",
        "## Limitations",
        "",
        "- This design is not fabrication-ready. Process DRC, EM cross-check, and expert review are required.",
        "- IDC connectivity is checked from deterministic generator net metadata; full polygon connectivity extraction is not implemented in this MVP.",
    ]
    if is_jpa and not physics_verified:
        lines.append(
            "- Overall physics verification is withheld until extraction and circuit tolerances both pass."
        )
    return "\n".join(lines).rstrip() + "\n"
