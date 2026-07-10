"""Callable registry for all 157 items in the Text-to-GDS improvement list."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import import_module
from typing import Any


@dataclass(frozen=True)
class Improvement:
    id: int
    name: str
    implementation: str
    level: str = "implemented"

    def resolve(self) -> Any:
        module_name, attribute = self.implementation.split(":", 1)
        return getattr(import_module(module_name), attribute)


_ROWS = [
    (1, "Superconducting LVS", "textlayout._legacy.verification:run_superconducting_lvs"),
    (2, "GDS equivalent-circuit extraction", "textlayout._legacy.verification:extract_circuit_from_gds"),
    (3, "SPICE netlist generation from GDS", "textlayout._legacy.verification:generate_spice_netlist"),
    (4, "JosephsonCircuits.jl model generation", "textlayout._legacy.verification:generate_josephsoncircuits_model"),
    (5, "Universal GDS to 3D model", "textlayout._legacy.em_extensions:build_universal_3d_model"),
    (6, "Superconducting PDK version control", "textlayout._legacy.pdk:PDKDatabase"),
    (7, "Git-like chip version tracking", "textlayout._legacy.verification:design_version_diff"),
    (8, "GDS visual diff", "textlayout._legacy.verification:gds_visual_diff"),
    (9, "Wafer-level mask generator", "textlayout._legacy.verification:generate_wafer_mask"),
    (10, "Dicing lanes and alignment marks", "textlayout._legacy.verification:generate_wafer_mask"),
    (11, "Fabrication process database", "textlayout._legacy.process_database:ProcessDatabase"),
    (12, "Wafer run tracking", "textlayout._legacy.fabrication:record_wafer_run"),
    (13, "JJ fabrication history database", "textlayout._legacy.fabrication:record_junction_measurement"),
    (14, "Oxidation recipe database", "textlayout._legacy.fabrication:record_oxidation_recipe"),
    (15, "Wafer-position Ic prediction", "textlayout._legacy.fabrication:predict_wafer_ic"),
    (16, "Fabrication yield prediction", "textlayout._legacy.fabrication:fabrication_yield_prediction"),
    (17, "Monte-Carlo process variation", "textlayout._legacy.uncertainty:run_process_monte_carlo"),
    (18, "SEM fabrication-error extraction", "textlayout._legacy.fabrication:compare_sem_images"),
    (19, "SEM versus GDS comparison", "textlayout._legacy.fabrication:compare_sem_images"),
    (20, "SEM critical-dimension measurement", "textlayout._legacy.fabrication:measure_sem_critical_dimensions"),
    (21, "Superconducting material database", "textlayout._legacy.physics_extensions:superconducting_material_database"),
    (22, "Kinetic inductance model", "textlayout._legacy.superconductivity:sheet_kinetic_inductance_ph"),
    (23, "London penetration-depth model", "textlayout._legacy.superconductivity:sheet_kinetic_inductance_ph"),
    (24, "Surface impedance model", "textlayout._legacy.physics_extensions:surface_impedance_model"),
    (25, "Superconducting loss model", "textlayout._legacy.physics_extensions:superconducting_loss"),
    (26, "Dielectric-loss participation", "textlayout._legacy.physics_extensions:dielectric_loss_participation"),
    (27, "Current-crowding simulation", "textlayout._legacy.superconductivity:current_crowding_profile"),
    (28, "Vortex-trapping prediction", "textlayout._legacy.physics_extensions:vortex_trapping_risk"),
    (29, "Magnetic-field compatibility", "textlayout._legacy.physics_extensions:magnetic_field_compatibility"),
    (30, "Flux-hole optimization", "textlayout._legacy.physics_extensions:optimize_flux_holes"),
    (31, "CPW impedance optimizer", "textlayout._legacy.physics_extensions:optimize_cpw_impedance"),
    (32, "IDC capacitor optimizer", "textlayout._legacy.physics_extensions:optimize_idc_capacitor"),
    (33, "Coupling-capacitor optimizer", "textlayout._legacy.physics_extensions:optimize_coupling_capacitor"),
    (34, "Resonator-length tuning", "textlayout._legacy.physics_extensions:tune_resonator_length"),
    (35, "Distributed transmission-line model", "textlayout._legacy.physics_extensions:distributed_transmission_line"),
    (36, "Package-level simulation", "textlayout._legacy.package_model:estimate_package_model"),
    (37, "PCB and chip co-design", "textlayout._legacy.physics_extensions:pcb_chip_codesign"),
    (38, "Wirebond inductance extraction", "textlayout._legacy.package_model:bondwire_inductance_nh"),
    (39, "Package cavity-mode prediction", "textlayout._legacy.package_model:rectangular_cavity_modes_ghz"),
    (40, "Connector-transition simulation", "textlayout._legacy.physics_extensions:connector_transition_simulation"),
    (41, "Universal EM solver interface", "textlayout._legacy.em_solvers:get_em_solver"),
    (42, "EM solver comparison", "textlayout._legacy.em_extensions:compare_em_solvers"),
    (43, "Mesh convergence test", "textlayout._legacy.em_extensions:mesh_convergence_analysis"),
    (44, "Adaptive mesh optimization", "textlayout._legacy.em_extensions:adaptive_mesh_plan"),
    (45, "Simulation error estimation", "textlayout._legacy.em_extensions:em_error_estimate"),
    (46, "EM validation checklist", "textlayout._legacy.em_extensions:validate_em_result"),
    (47, "Automatic S-parameter fitting", "textlayout._legacy.fitting:fit_trace"),
    (48, "Vector fitting", "textlayout._legacy.em_extensions:vector_fit"),
    (49, "Rational model extraction", "textlayout._legacy.em_extensions:vector_fit"),
    (50, "Reduced-order model generation", "textlayout._legacy.em_extensions:reduced_order_model"),
    (51, "Lumped-element fitting", "textlayout._legacy.em_extensions:lumped_element_fit"),
    (52, "EM-to-circuit feedback", "textlayout._legacy.em_extensions:em_to_circuit_feedback"),
    (53, "EM database cache", "textlayout._legacy.em_extensions:cache_em_result"),
    (54, "Simulation result version control", "textlayout._legacy.em_extensions:cache_em_result"),
    (55, "Hamiltonian extraction", "textlayout._legacy.quantum_extensions:extract_hamiltonian"),
    (56, "Black-box quantization", "textlayout._legacy.quantum_extensions:black_box_quantization"),
    (57, "Energy participation workflow", "textlayout._legacy.epr:write_epr_analysis"),
    (58, "pyEPR automatic pipeline", "textlayout._legacy.epr:write_epr_analysis"),
    (59, "Multimode coupling extraction", "textlayout._legacy.quantum_extensions:multimode_coupling"),
    (60, "Cross-Kerr calculation", "textlayout._legacy.quantum_extensions:black_box_quantization"),
    (61, "Self-Kerr calculation", "textlayout._legacy.quantum_extensions:black_box_quantization"),
    (62, "Anharmonicity extraction", "textlayout._legacy.quantum_extensions:extract_hamiltonian"),
    (63, "Qubit lifetime prediction", "textlayout._legacy.quantum_extensions:qubit_lifetime_prediction"),
    (64, "Purcell loss", "textlayout._legacy.quantum_extensions:purcell_lifetime_s"),
    (65, "Radiation loss", "textlayout._legacy.quantum_extensions:radiation_lifetime_s"),
    (66, "Complete Kerr JPA model", "textlayout._legacy.theory.kerr_jpa:kerr_jpa_gain"),
    (67, "Duffing oscillator solver", "textlayout._legacy.nonlinear_extensions:solve_duffing_steady_state"),
    (68, "Three-wave mixing", "textlayout._legacy.theory.three_wave_mixing:three_wave_mixing_gain"),
    (69, "Four-wave mixing", "textlayout._legacy.theory.four_wave_mixing:four_wave_mixing_gain"),
    (70, "SNAIL amplifier", "textlayout._legacy.nonlinear_extensions:amplifier_model"),
    (71, "IMPA", "textlayout._legacy.nonlinear_extensions:amplifier_model"),
    (72, "KIT amplifier", "textlayout._legacy.nonlinear_extensions:amplifier_model"),
    (73, "TWPA unit-cell generator", "textlayout._legacy.pcells.traveling_wave:periodically_loaded_kit_unit_cell"),
    (74, "TWPA dispersion engineering", "textlayout._legacy.jtwpa:jtwpa_bloch_wavenumber"),
    (75, "Phase-matching optimizer", "textlayout._legacy.nonlinear_extensions:phase_matching_optimizer"),
    (76, "Pump depletion", "textlayout._legacy.nonlinear_extensions:pump_depletion_model"),
    (77, "Nonlinear saturation", "textlayout._legacy.nonlinear_extensions:nonlinear_saturation"),
    (78, "Bifurcation detection", "textlayout._legacy.nonlinear_extensions:solve_duffing_steady_state"),
    (79, "Stability map", "textlayout._legacy.nonlinear_extensions:stability_map"),
    (80, "Gain ripple analysis", "textlayout._legacy.nonlinear_extensions:gain_ripple_analysis"),
    (81, "Impedance mismatch analysis", "textlayout._legacy.nonlinear_extensions:impedance_mismatch_analysis"),
    (82, "Standing-wave simulation", "textlayout._legacy.nonlinear_extensions:standing_wave_effect"),
    (83, "Pump leakage analysis", "textlayout._legacy.nonlinear_extensions:pump_leakage"),
    (84, "Pump cancellation design", "textlayout._legacy.nonlinear_extensions:pump_cancellation_design"),
    (85, "Dynamic-range optimizer", "textlayout._legacy.nonlinear_extensions:optimize_dynamic_range"),
    (86, "Instrument drivers", "textlayout._legacy.measurement_extensions:instrument_driver"),
    (87, "Automatic VNA calibration", "textlayout._legacy.measurement_extensions:apply_vna_calibration"),
    (88, "SOLT calibration", "textlayout._legacy.measurement_extensions:solt_calibration"),
    (89, "TRL calibration", "textlayout._legacy.measurement_extensions:trl_calibration"),
    (90, "Power calibration", "textlayout._legacy.measurement_extensions:power_calibration"),
    (91, "Automatic resonance finder", "textlayout._legacy.measurement_extensions:find_resonance"),
    (92, "Automatic pump optimizer", "textlayout._legacy.measurement_extensions:optimize_measurement_axis"),
    (93, "Automatic flux optimizer", "textlayout._legacy.measurement_extensions:optimize_measurement_axis"),
    (94, "Automatic gain measurement", "textlayout._legacy.measurement_extensions:measure_gain"),
    (95, "Automatic bandwidth extraction", "textlayout._legacy.measurement_extensions:extract_bandwidth"),
    (96, "Automatic P1dB measurement", "textlayout._legacy.measurement_extensions:extract_p1db"),
    (97, "Two-tone IP3", "textlayout._legacy.measurement_extensions:extract_ip3"),
    (98, "Noise-temperature measurement", "textlayout._legacy.measurement_extensions:y_factor_noise_temperature"),
    (99, "Y-factor calibration", "textlayout._legacy.measurement_extensions:y_factor_noise_temperature"),
    (100, "Quantum-efficiency extraction", "textlayout._legacy.measurement_extensions:quantum_efficiency"),
    (101, "Squeezing analysis", "textlayout._legacy.measurement_extensions:squeezing_analysis"),
    (102, "IQ histogram", "textlayout._legacy.measurement_extensions:iq_histogram"),
    (103, "Wigner reconstruction", "textlayout._legacy.measurement_extensions:reconstruct_wigner"),
    (104, "Long-term stability", "textlayout._legacy.measurement_extensions:long_term_stability"),
    (105, "Drift analysis", "textlayout._legacy.measurement_extensions:drift_analysis"),
    (106, "Dilution refrigerator model", "textlayout._legacy.platform_extensions:dilution_refrigerator_model"),
    (107, "Cryogenic cable database", "textlayout._legacy.platform_extensions:cryogenic_cable_database"),
    (108, "Attenuator thermal model", "textlayout._legacy.platform_extensions:attenuator_thermal_model"),
    (109, "Circulator loss model", "textlayout._legacy.platform_extensions:passive_component_noise"),
    (110, "HEMT amplifier model", "textlayout._legacy.platform_extensions:hemt_amplifier_model"),
    (111, "Friis noise", "textlayout._legacy.platform_extensions:friis_noise"),
    (112, "Complete noise budget", "textlayout._legacy.platform_extensions:friis_noise"),
    (113, "Pump power budget", "textlayout._legacy.platform_extensions:pump_power_budget"),
    (114, "Measurement-chain optimizer", "textlayout._legacy.platform_extensions:optimize_measurement_chain"),
    (115, "AI design reviewer", "textlayout._legacy.platform_extensions:ai_design_reviewer"),
    (116, "AI physics checker", "textlayout._legacy.platform_extensions:ai_physics_checker"),
    (117, "AI fabrication checker", "textlayout._legacy.platform_extensions:ai_fabrication_checker"),
    (118, "AI measurement assistant", "textlayout._legacy.platform_extensions:ai_measurement_assistant"),
    (119, "Multi-agent workflow", "textlayout._legacy.platform_extensions:multi_agent_workflow"),
    (120, "Autonomous design iteration", "textlayout._legacy.platform_extensions:autonomous_design_iteration"),
    (121, "Reinforcement-learning optimizer", "textlayout._legacy.platform_extensions:reinforcement_learning_optimizer"),
    (122, "Bayesian optimization from prior chips", "textlayout._legacy.platform_extensions:bayesian_design_prediction"),
    (123, "Failure-analysis agent", "textlayout._legacy.platform_extensions:failure_analysis"),
    (124, "Paper-comparison agent", "textlayout._legacy.platform_extensions:compare_with_paper"),
    (125, "Literature parameter extraction", "textlayout._legacy.platform_extensions:extract_literature_parameters"),
    (126, "Device database", "textlayout._legacy.platform_extensions:index_record"),
    (127, "Experiment database", "textlayout._legacy.experiment_database:record_experiment"),
    (128, "Simulation database", "textlayout._legacy.platform_extensions:index_record"),
    (129, "Fabrication database", "textlayout._legacy.fabrication:initialize_fabrication_database"),
    (130, "Measurement database", "textlayout._legacy.platform_extensions:index_record"),
    (131, "Search previous designs", "textlayout._legacy.platform_extensions:search_records"),
    (132, "Similarity search", "textlayout._legacy.platform_extensions:similarity_search"),
    (133, "Device vector database", "textlayout._legacy.platform_extensions:similarity_search"),
    (134, "Automatic report indexing", "textlayout._legacy.platform_extensions:index_record"),
    (135, "Nature figure style", "textlayout._legacy.platform_extensions:figure_style"),
    (136, "IEEE TAS figure style", "textlayout._legacy.platform_extensions:figure_style"),
    (137, "PRX figure style", "textlayout._legacy.platform_extensions:figure_style"),
    (138, "Automatic caption generation", "textlayout._legacy.platform_extensions:generate_caption"),
    (139, "Device comparison table", "textlayout._legacy.platform_extensions:device_comparison_table"),
    (140, "Automatic benchmark reproduction", "textlayout._legacy.paper_benchmarks:run_paper_benchmark_suite"),
    (141, "Paper parameter extraction", "textlayout._legacy.platform_extensions:extract_literature_parameters"),
    (142, "DOI-linked benchmark database", "textlayout._legacy.platform_extensions:doi_benchmark_record"),
    (143, "Citation graph", "textlayout._legacy.platform_extensions:citation_graph"),
    (144, "Plugin architecture", "textlayout._legacy.platform_extensions:plugin_manifest"),
    (145, "Docker environment", "textlayout._legacy.platform_extensions:docker_environment"),
    (146, "Cloud simulation worker", "textlayout._legacy.platform_extensions:cloud_worker_job", "prepared_adapter"),
    (147, "REST API backend", "textlayout._legacy.platform_extensions:rest_api_spec"),
    (148, "Web dashboard", "textlayout._legacy.ui:serve_workbench"),
    (149, "Collaborative design workspace", "textlayout._legacy.platform_extensions:collaborative_workspace_event"),
    (150, "Permission system", "textlayout._legacy.platform_extensions:authorize"),
    (151, "CI/CD simulation testing", "textlayout._legacy.platform_extensions:ci_pipeline"),
    (152, "Automatic regression tests", "textlayout._legacy.platform_extensions:regression_test_case"),
    (153, "Device benchmark tests", "textlayout._legacy.platform_extensions:benchmark_test_case"),
    (154, "Documentation generator", "textlayout._legacy.platform_extensions:generate_api_documentation"),
    (155, "Example gallery", "textlayout._legacy.platform_extensions:example_gallery"),
    (156, "Tutorial notebooks", "textlayout._legacy.platform_extensions:tutorial_notebook"),
    (157, "Complete closed loop", "textlayout._legacy.platform_extensions:closed_loop_platform"),
]


IMPROVEMENTS = {
    row[0]: Improvement(row[0], row[1], row[2], row[3] if len(row) > 3 else "implemented")
    for row in _ROWS
}


def list_improvements() -> dict[str, Any]:
    return {
        "schema": "text-to-gds.improvement-registry.v1",
        "count": len(IMPROVEMENTS),
        "unique_implementations": len({item.implementation for item in IMPROVEMENTS.values()}),
        "features": [asdict(IMPROVEMENTS[index]) for index in sorted(IMPROVEMENTS)],
    }


def validate_improvement_registry() -> dict[str, Any]:
    expected = set(range(1, 158))
    missing = sorted(expected - IMPROVEMENTS.keys())
    unresolved = []
    for feature in IMPROVEMENTS.values():
        try:
            implementation = feature.resolve()
            if not callable(implementation):
                unresolved.append({"id": feature.id, "error": "implementation is not callable"})
        except (ImportError, AttributeError) as exc:
            unresolved.append({"id": feature.id, "error": str(exc)})
    return {"passed": not missing and not unresolved, "missing": missing, "unresolved": unresolved, "count": len(IMPROVEMENTS)}


def call_improvement(feature_id: int, **kwargs: Any) -> Any:
    if feature_id not in IMPROVEMENTS:
        raise KeyError(f"Unknown improvement {feature_id}")
    implementation = IMPROVEMENTS[feature_id].resolve()
    if not callable(implementation):
        if kwargs:
            raise TypeError(f"Improvement {feature_id} is data, not a callable")
        return implementation
    return implementation(**kwargs)
