"""Callable registry for the 37 third-wave autonomous-scientist capabilities."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import import_module
from typing import Any


@dataclass(frozen=True)
class ThirdWaveImprovement:
    id: int
    name: str
    implementation: str
    level: str = "implemented"

    def resolve(self) -> Any:
        module, attribute = self.implementation.split(":", 1)
        return getattr(import_module(module), attribute)


_ROWS = [
    (1, "Differentiable EM solver", "textlayout._legacy.inverse_design:DifferentiableEMSolver"),
    (2, "Differentiable GDS pipeline", "textlayout._legacy.inverse_design:DifferentiableGDSPipeline"),
    (3, "Adjoint optimization", "textlayout._legacy.inverse_design:linear_adjoint_gradient"),
    (4, "Neural-operator EM model", "textlayout._legacy.inverse_design:train_neural_operator"),
    (5, "Microwave-circuit foundation model", "textlayout._legacy.inverse_design:train_microwave_foundation_model"),
    (6, "Automatic topology invention", "textlayout._legacy.scientist_extensions:invent_circuit_topologies"),
    (7, "Circuit genetic evolution", "textlayout._legacy.scientist_extensions:evolve_circuits"),
    (8, "Symbolic microwave reasoning", "textlayout._legacy.scientist_extensions:symbolic_microwave_reasoning"),
    (9, "Equation discovery", "textlayout._legacy.scientist_extensions:discover_equation"),
    (10, "Automatic approximation selection", "textlayout._legacy.scientist_extensions:select_approximation"),
    (11, "Full cryostat digital twin", "textlayout._legacy.scientist_extensions:full_cryostat_twin"),
    (12, "Complete noise propagation", "textlayout._legacy.research_automation:propagate_quantum_noise"),
    (13, "Thermal-photon simulator", "textlayout._legacy.research_automation:thermal_photon_analysis"),
    (14, "Magnetic-shielding simulator", "textlayout._legacy.scientist_extensions:magnetic_shielding_simulator"),
    (15, "Vibration-effect model", "textlayout._legacy.scientist_extensions:vibration_effect_model"),
    (16, "Cooldown failure prediction", "textlayout._legacy.scientist_extensions:predict_cooldown_failure"),
    (17, "SEM image understanding", "textlayout._legacy.scientist_extensions:understand_sem_image"),
    (18, "Microscope-to-GDS alignment", "textlayout._legacy.scientist_extensions:align_microscope_to_gds"),
    (19, "AI wafer-yield prediction", "textlayout._legacy.scientist_extensions:predict_wafer_yield_ai"),
    (20, "Fabrication root-cause analysis", "textlayout._legacy.scientist_extensions:fabrication_root_cause"),
    (21, "Autonomous literature watcher", "textlayout._legacy.scientist_extensions:literature_watcher", "prepared_adapter"),
    (22, "Paper-to-executable model", "textlayout._legacy.scientist_extensions:paper_to_executable_model", "prepared_adapter"),
    (23, "Equation verification", "textlayout._legacy.scientist_extensions:verify_equation"),
    (24, "Scientific claim checker", "textlayout._legacy.scientist_extensions:check_amplifier_claim"),
    (25, "Autonomous VNA tuning", "textlayout._legacy.scientist_extensions:autonomous_vna_tuning", "hardware_adapter"),
    (26, "Bayesian experiment planning", "textlayout._legacy.scientist_extensions:bayesian_experiment_plan"),
    (27, "Reinforcement-learning JPA tuning", "textlayout._legacy.scientist_extensions:reinforcement_learning_jpa_tuning"),
    (28, "Automatic failure diagnosis", "textlayout._legacy.scientist_extensions:diagnose_no_gain"),
    (29, "Tapeout checklist", "textlayout._legacy.scientist_extensions:tapeout_checklist"),
    (30, "Mask-review AI", "textlayout._legacy.scientist_extensions:mask_review_ai"),
    (31, "Superconducting-circuit LVS", "textlayout._legacy.verification:run_superconducting_lvs"),
    (32, "Electromagnetic DFM", "textlayout._legacy.scientist_extensions:electromagnetic_dfm"),
    (33, "Design-review meeting report", "textlayout._legacy.scientist_extensions:design_review_meeting_report"),
    (34, "Quantum-device leaderboard", "textlayout._legacy.scientist_extensions:quantum_device_leaderboard"),
    (35, "Reproduction score", "textlayout._legacy.scientist_extensions:reproduction_score"),
    (36, "Multi-agent research lab", "textlayout._legacy.scientist_extensions:multi_agent_research_lab"),
    (37, "Autonomous quantum-device scientist", "textlayout._legacy.scientist_extensions:autonomous_quantum_scientist"),
]


THIRD_WAVE_IMPROVEMENTS = {
    row[0]: ThirdWaveImprovement(row[0], row[1], row[2], row[3] if len(row) > 3 else "implemented")
    for row in _ROWS
}


def _unique_platform_implementations() -> int:
    """Count distinct implementation targets across all three registries.

    The catalog has 340 numbered entries, but several entries intentionally
    map to the same underlying function (e.g. wafer dicing lanes and alignment
    marks both resolve to ``generate_wafer_mask``). This reports the honest
    number of distinct callables behind the catalog.
    """
    from textlayout._legacy.improvements import IMPROVEMENTS
    from textlayout._legacy.next_improvements import NEXT_IMPROVEMENTS

    targets = {item.implementation for item in IMPROVEMENTS.values()}
    targets |= {item.implementation for item in NEXT_IMPROVEMENTS.values()}
    targets |= {item.implementation for item in THIRD_WAVE_IMPROVEMENTS.values()}
    return len(targets)


def list_third_wave_improvements() -> dict[str, Any]:
    return {"schema": "text-to-gds.third-wave-registry.v1", "count": len(THIRD_WAVE_IMPROVEMENTS), "total_platform_capabilities": 157 + 146 + len(THIRD_WAVE_IMPROVEMENTS), "unique_platform_implementations": _unique_platform_implementations(), "features": [asdict(THIRD_WAVE_IMPROVEMENTS[index]) for index in sorted(THIRD_WAVE_IMPROVEMENTS)]}


def validate_third_wave_registry() -> dict[str, Any]:
    missing = sorted(set(range(1, 38)) - THIRD_WAVE_IMPROVEMENTS.keys())
    unresolved = []
    for feature in THIRD_WAVE_IMPROVEMENTS.values():
        try:
            if not callable(feature.resolve()):
                unresolved.append({"id": feature.id, "error": "implementation is not callable"})
        except (ImportError, AttributeError, SyntaxError) as exc:
            unresolved.append({"id": feature.id, "error": str(exc)})
    return {"passed": not missing and not unresolved, "count": len(THIRD_WAVE_IMPROVEMENTS), "missing": missing, "unresolved": unresolved}


def call_third_wave_improvement(feature_id: int, **kwargs: Any) -> Any:
    if feature_id not in THIRD_WAVE_IMPROVEMENTS:
        raise KeyError(f"Unknown third-wave improvement {feature_id}")
    return THIRD_WAVE_IMPROVEMENTS[feature_id].resolve()(**kwargs)
