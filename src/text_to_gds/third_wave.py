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
    (1, "Differentiable EM solver", "text_to_gds.inverse_design:DifferentiableEMSolver"),
    (2, "Differentiable GDS pipeline", "text_to_gds.inverse_design:DifferentiableGDSPipeline"),
    (3, "Adjoint optimization", "text_to_gds.inverse_design:linear_adjoint_gradient"),
    (4, "Neural-operator EM model", "text_to_gds.inverse_design:train_neural_operator"),
    (5, "Microwave-circuit foundation model", "text_to_gds.inverse_design:train_microwave_foundation_model"),
    (6, "Automatic topology invention", "text_to_gds.scientist_extensions:invent_circuit_topologies"),
    (7, "Circuit genetic evolution", "text_to_gds.scientist_extensions:evolve_circuits"),
    (8, "Symbolic microwave reasoning", "text_to_gds.scientist_extensions:symbolic_microwave_reasoning"),
    (9, "Equation discovery", "text_to_gds.scientist_extensions:discover_equation"),
    (10, "Automatic approximation selection", "text_to_gds.scientist_extensions:select_approximation"),
    (11, "Full cryostat digital twin", "text_to_gds.scientist_extensions:full_cryostat_twin"),
    (12, "Complete noise propagation", "text_to_gds.research_automation:propagate_quantum_noise"),
    (13, "Thermal-photon simulator", "text_to_gds.research_automation:thermal_photon_analysis"),
    (14, "Magnetic-shielding simulator", "text_to_gds.scientist_extensions:magnetic_shielding_simulator"),
    (15, "Vibration-effect model", "text_to_gds.scientist_extensions:vibration_effect_model"),
    (16, "Cooldown failure prediction", "text_to_gds.scientist_extensions:predict_cooldown_failure"),
    (17, "SEM image understanding", "text_to_gds.scientist_extensions:understand_sem_image"),
    (18, "Microscope-to-GDS alignment", "text_to_gds.scientist_extensions:align_microscope_to_gds"),
    (19, "AI wafer-yield prediction", "text_to_gds.scientist_extensions:predict_wafer_yield_ai"),
    (20, "Fabrication root-cause analysis", "text_to_gds.scientist_extensions:fabrication_root_cause"),
    (21, "Autonomous literature watcher", "text_to_gds.scientist_extensions:literature_watcher", "prepared_adapter"),
    (22, "Paper-to-executable model", "text_to_gds.scientist_extensions:paper_to_executable_model", "prepared_adapter"),
    (23, "Equation verification", "text_to_gds.scientist_extensions:verify_equation"),
    (24, "Scientific claim checker", "text_to_gds.scientist_extensions:check_amplifier_claim"),
    (25, "Autonomous VNA tuning", "text_to_gds.scientist_extensions:autonomous_vna_tuning", "hardware_adapter"),
    (26, "Bayesian experiment planning", "text_to_gds.scientist_extensions:bayesian_experiment_plan"),
    (27, "Reinforcement-learning JPA tuning", "text_to_gds.scientist_extensions:reinforcement_learning_jpa_tuning"),
    (28, "Automatic failure diagnosis", "text_to_gds.scientist_extensions:diagnose_no_gain"),
    (29, "Tapeout checklist", "text_to_gds.scientist_extensions:tapeout_checklist"),
    (30, "Mask-review AI", "text_to_gds.scientist_extensions:mask_review_ai"),
    (31, "Superconducting-circuit LVS", "text_to_gds.verification:run_superconducting_lvs"),
    (32, "Electromagnetic DFM", "text_to_gds.scientist_extensions:electromagnetic_dfm"),
    (33, "Design-review meeting report", "text_to_gds.scientist_extensions:design_review_meeting_report"),
    (34, "Quantum-device leaderboard", "text_to_gds.scientist_extensions:quantum_device_leaderboard"),
    (35, "Reproduction score", "text_to_gds.scientist_extensions:reproduction_score"),
    (36, "Multi-agent research lab", "text_to_gds.scientist_extensions:multi_agent_research_lab"),
    (37, "Autonomous quantum-device scientist", "text_to_gds.scientist_extensions:autonomous_quantum_scientist"),
]


THIRD_WAVE_IMPROVEMENTS = {
    row[0]: ThirdWaveImprovement(row[0], row[1], row[2], row[3] if len(row) > 3 else "implemented")
    for row in _ROWS
}


def list_third_wave_improvements() -> dict[str, Any]:
    return {"schema": "text-to-gds.third-wave-registry.v1", "count": len(THIRD_WAVE_IMPROVEMENTS), "total_platform_capabilities": 157 + 146 + len(THIRD_WAVE_IMPROVEMENTS), "features": [asdict(THIRD_WAVE_IMPROVEMENTS[index]) for index in sorted(THIRD_WAVE_IMPROVEMENTS)]}


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
