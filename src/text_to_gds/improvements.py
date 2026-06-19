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
    (1, "Superconducting LVS", "text_to_gds.verification:run_superconducting_lvs"),
    (2, "GDS equivalent-circuit extraction", "text_to_gds.verification:extract_circuit_from_gds"),
    (3, "SPICE netlist generation from GDS", "text_to_gds.verification:generate_spice_netlist"),
    (4, "JosephsonCircuits.jl model generation", "text_to_gds.verification:generate_josephsoncircuits_model"),
    (5, "Universal GDS to 3D model", "text_to_gds.em_extensions:build_universal_3d_model"),
    (6, "Superconducting PDK version control", "text_to_gds.pdk:PDKDatabase"),
    (7, "Git-like chip version tracking", "text_to_gds.verification:design_version_diff"),
    (8, "GDS visual diff", "text_to_gds.verification:gds_visual_diff"),
    (9, "Wafer-level mask generator", "text_to_gds.verification:generate_wafer_mask"),
    (10, "Dicing lanes and alignment marks", "text_to_gds.verification:generate_wafer_mask"),
    (11, "Fabrication process database", "text_to_gds.process_database:ProcessDatabase"),
    (12, "Wafer run tracking", "text_to_gds.fabrication:record_wafer_run"),
    (13, "JJ fabrication history database", "text_to_gds.fabrication:record_junction_measurement"),
    (14, "Oxidation recipe database", "text_to_gds.fabrication:record_oxidation_recipe"),
    (15, "Wafer-position Ic prediction", "text_to_gds.fabrication:predict_wafer_ic"),
    (16, "Fabrication yield prediction", "text_to_gds.fabrication:fabrication_yield_prediction"),
    (17, "Monte-Carlo process variation", "text_to_gds.uncertainty:run_process_monte_carlo"),
    (18, "SEM fabrication-error extraction", "text_to_gds.fabrication:compare_sem_images"),
    (19, "SEM versus GDS comparison", "text_to_gds.fabrication:compare_sem_images"),
    (20, "SEM critical-dimension measurement", "text_to_gds.fabrication:measure_sem_critical_dimensions"),
    (21, "Superconducting material database", "text_to_gds.physics_extensions:superconducting_material_database"),
    (22, "Kinetic inductance model", "text_to_gds.superconductivity:sheet_kinetic_inductance_ph"),
    (23, "London penetration-depth model", "text_to_gds.superconductivity:sheet_kinetic_inductance_ph"),
    (24, "Surface impedance model", "text_to_gds.physics_extensions:surface_impedance_model"),
    (25, "Superconducting loss model", "text_to_gds.physics_extensions:superconducting_loss"),
    (26, "Dielectric-loss participation", "text_to_gds.physics_extensions:dielectric_loss_participation"),
    (27, "Current-crowding simulation", "text_to_gds.superconductivity:current_crowding_profile"),
    (28, "Vortex-trapping prediction", "text_to_gds.physics_extensions:vortex_trapping_risk"),
    (29, "Magnetic-field compatibility", "text_to_gds.physics_extensions:magnetic_field_compatibility"),
    (30, "Flux-hole optimization", "text_to_gds.physics_extensions:optimize_flux_holes"),
    (31, "CPW impedance optimizer", "text_to_gds.physics_extensions:optimize_cpw_impedance"),
    (32, "IDC capacitor optimizer", "text_to_gds.physics_extensions:optimize_idc_capacitor"),
    (33, "Coupling-capacitor optimizer", "text_to_gds.physics_extensions:optimize_coupling_capacitor"),
    (34, "Resonator-length tuning", "text_to_gds.physics_extensions:tune_resonator_length"),
    (35, "Distributed transmission-line model", "text_to_gds.physics_extensions:distributed_transmission_line"),
    (36, "Package-level simulation", "text_to_gds.package_model:estimate_package_model"),
    (37, "PCB and chip co-design", "text_to_gds.physics_extensions:pcb_chip_codesign"),
    (38, "Wirebond inductance extraction", "text_to_gds.package_model:bondwire_inductance_nh"),
    (39, "Package cavity-mode prediction", "text_to_gds.package_model:rectangular_cavity_modes_ghz"),
    (40, "Connector-transition simulation", "text_to_gds.physics_extensions:connector_transition_simulation"),
    (41, "Universal EM solver interface", "text_to_gds.em_solvers:get_em_solver"),
    (42, "EM solver comparison", "text_to_gds.em_extensions:compare_em_solvers"),
    (43, "Mesh convergence test", "text_to_gds.em_extensions:mesh_convergence_analysis"),
    (44, "Adaptive mesh optimization", "text_to_gds.em_extensions:adaptive_mesh_plan"),
    (45, "Simulation error estimation", "text_to_gds.em_extensions:em_error_estimate"),
    (46, "EM validation checklist", "text_to_gds.em_extensions:validate_em_result"),
    (47, "Automatic S-parameter fitting", "text_to_gds.fitting:fit_trace"),
    (48, "Vector fitting", "text_to_gds.em_extensions:vector_fit"),
    (49, "Rational model extraction", "text_to_gds.em_extensions:vector_fit"),
    (50, "Reduced-order model generation", "text_to_gds.em_extensions:reduced_order_model"),
    (51, "Lumped-element fitting", "text_to_gds.em_extensions:lumped_element_fit"),
    (52, "EM-to-circuit feedback", "text_to_gds.em_extensions:em_to_circuit_feedback"),
    (53, "EM database cache", "text_to_gds.em_extensions:cache_em_result"),
    (54, "Simulation result version control", "text_to_gds.em_extensions:cache_em_result"),
    (55, "Hamiltonian extraction", "text_to_gds.quantum_extensions:extract_hamiltonian"),
    (56, "Black-box quantization", "text_to_gds.quantum_extensions:black_box_quantization"),
    (57, "Energy participation workflow", "text_to_gds.epr:write_epr_analysis"),
    (58, "pyEPR automatic pipeline", "text_to_gds.epr:write_epr_analysis"),
    (59, "Multimode coupling extraction", "text_to_gds.quantum_extensions:multimode_coupling"),
    (60, "Cross-Kerr calculation", "text_to_gds.quantum_extensions:black_box_quantization"),
    (61, "Self-Kerr calculation", "text_to_gds.quantum_extensions:black_box_quantization"),
    (62, "Anharmonicity extraction", "text_to_gds.quantum_extensions:extract_hamiltonian"),
    (63, "Qubit lifetime prediction", "text_to_gds.quantum_extensions:qubit_lifetime_prediction"),
    (64, "Purcell loss", "text_to_gds.quantum_extensions:purcell_lifetime_s"),
    (65, "Radiation loss", "text_to_gds.quantum_extensions:radiation_lifetime_s"),
    (66, "Complete Kerr JPA model", "text_to_gds.theory.kerr_jpa:kerr_jpa_gain"),
    (67, "Duffing oscillator solver", "text_to_gds.nonlinear_extensions:solve_duffing_steady_state"),
    (68, "Three-wave mixing", "text_to_gds.theory.three_wave_mixing:three_wave_mixing_gain"),
    (69, "Four-wave mixing", "text_to_gds.theory.four_wave_mixing:four_wave_mixing_gain"),
    (70, "SNAIL amplifier", "text_to_gds.nonlinear_extensions:amplifier_model"),
    (71, "IMPA", "text_to_gds.nonlinear_extensions:amplifier_model"),
    (72, "KIT amplifier", "text_to_gds.nonlinear_extensions:amplifier_model"),
    (73, "TWPA unit-cell generator", "text_to_gds.pcells.traveling_wave:periodically_loaded_kit_unit_cell"),
    (74, "TWPA dispersion engineering", "text_to_gds.jtwpa:jtwpa_bloch_wavenumber"),
    (75, "Phase-matching optimizer", "text_to_gds.nonlinear_extensions:phase_matching_optimizer"),
    (76, "Pump depletion", "text_to_gds.nonlinear_extensions:pump_depletion_model"),
    (77, "Nonlinear saturation", "text_to_gds.nonlinear_extensions:nonlinear_saturation"),
    (78, "Bifurcation detection", "text_to_gds.nonlinear_extensions:solve_duffing_steady_state"),
    (79, "Stability map", "text_to_gds.nonlinear_extensions:stability_map"),
    (80, "Gain ripple analysis", "text_to_gds.nonlinear_extensions:gain_ripple_analysis"),
    (81, "Impedance mismatch analysis", "text_to_gds.nonlinear_extensions:impedance_mismatch_analysis"),
    (82, "Standing-wave simulation", "text_to_gds.nonlinear_extensions:standing_wave_effect"),
    (83, "Pump leakage analysis", "text_to_gds.nonlinear_extensions:pump_leakage"),
    (84, "Pump cancellation design", "text_to_gds.nonlinear_extensions:pump_cancellation_design"),
    (85, "Dynamic-range optimizer", "text_to_gds.nonlinear_extensions:optimize_dynamic_range"),
    (86, "Instrument drivers", "text_to_gds.measurement_extensions:instrument_driver"),
    (87, "Automatic VNA calibration", "text_to_gds.measurement_extensions:apply_vna_calibration"),
    (88, "SOLT calibration", "text_to_gds.measurement_extensions:solt_calibration"),
    (89, "TRL calibration", "text_to_gds.measurement_extensions:trl_calibration"),
    (90, "Power calibration", "text_to_gds.measurement_extensions:power_calibration"),
    (91, "Automatic resonance finder", "text_to_gds.measurement_extensions:find_resonance"),
    (92, "Automatic pump optimizer", "text_to_gds.measurement_extensions:optimize_measurement_axis"),
    (93, "Automatic flux optimizer", "text_to_gds.measurement_extensions:optimize_measurement_axis"),
    (94, "Automatic gain measurement", "text_to_gds.measurement_extensions:measure_gain"),
    (95, "Automatic bandwidth extraction", "text_to_gds.measurement_extensions:extract_bandwidth"),
    (96, "Automatic P1dB measurement", "text_to_gds.measurement_extensions:extract_p1db"),
    (97, "Two-tone IP3", "text_to_gds.measurement_extensions:extract_ip3"),
    (98, "Noise-temperature measurement", "text_to_gds.measurement_extensions:y_factor_noise_temperature"),
    (99, "Y-factor calibration", "text_to_gds.measurement_extensions:y_factor_noise_temperature"),
    (100, "Quantum-efficiency extraction", "text_to_gds.measurement_extensions:quantum_efficiency"),
    (101, "Squeezing analysis", "text_to_gds.measurement_extensions:squeezing_analysis"),
    (102, "IQ histogram", "text_to_gds.measurement_extensions:iq_histogram"),
    (103, "Wigner reconstruction", "text_to_gds.measurement_extensions:reconstruct_wigner"),
    (104, "Long-term stability", "text_to_gds.measurement_extensions:long_term_stability"),
    (105, "Drift analysis", "text_to_gds.measurement_extensions:drift_analysis"),
    (106, "Dilution refrigerator model", "text_to_gds.platform_extensions:dilution_refrigerator_model"),
    (107, "Cryogenic cable database", "text_to_gds.platform_extensions:cryogenic_cable_database"),
    (108, "Attenuator thermal model", "text_to_gds.platform_extensions:attenuator_thermal_model"),
    (109, "Circulator loss model", "text_to_gds.platform_extensions:passive_component_noise"),
    (110, "HEMT amplifier model", "text_to_gds.platform_extensions:hemt_amplifier_model"),
    (111, "Friis noise", "text_to_gds.platform_extensions:friis_noise"),
    (112, "Complete noise budget", "text_to_gds.platform_extensions:friis_noise"),
    (113, "Pump power budget", "text_to_gds.platform_extensions:pump_power_budget"),
    (114, "Measurement-chain optimizer", "text_to_gds.platform_extensions:optimize_measurement_chain"),
    (115, "AI design reviewer", "text_to_gds.platform_extensions:ai_design_reviewer"),
    (116, "AI physics checker", "text_to_gds.platform_extensions:ai_physics_checker"),
    (117, "AI fabrication checker", "text_to_gds.platform_extensions:ai_fabrication_checker"),
    (118, "AI measurement assistant", "text_to_gds.platform_extensions:ai_measurement_assistant"),
    (119, "Multi-agent workflow", "text_to_gds.platform_extensions:multi_agent_workflow"),
    (120, "Autonomous design iteration", "text_to_gds.platform_extensions:autonomous_design_iteration"),
    (121, "Reinforcement-learning optimizer", "text_to_gds.platform_extensions:reinforcement_learning_optimizer"),
    (122, "Bayesian optimization from prior chips", "text_to_gds.platform_extensions:bayesian_design_prediction"),
    (123, "Failure-analysis agent", "text_to_gds.platform_extensions:failure_analysis"),
    (124, "Paper-comparison agent", "text_to_gds.platform_extensions:compare_with_paper"),
    (125, "Literature parameter extraction", "text_to_gds.platform_extensions:extract_literature_parameters"),
    (126, "Device database", "text_to_gds.platform_extensions:index_record"),
    (127, "Experiment database", "text_to_gds.experiment_database:record_experiment"),
    (128, "Simulation database", "text_to_gds.platform_extensions:index_record"),
    (129, "Fabrication database", "text_to_gds.fabrication:initialize_fabrication_database"),
    (130, "Measurement database", "text_to_gds.platform_extensions:index_record"),
    (131, "Search previous designs", "text_to_gds.platform_extensions:search_records"),
    (132, "Similarity search", "text_to_gds.platform_extensions:similarity_search"),
    (133, "Device vector database", "text_to_gds.platform_extensions:similarity_search"),
    (134, "Automatic report indexing", "text_to_gds.platform_extensions:index_record"),
    (135, "Nature figure style", "text_to_gds.platform_extensions:figure_style"),
    (136, "IEEE TAS figure style", "text_to_gds.platform_extensions:figure_style"),
    (137, "PRX figure style", "text_to_gds.platform_extensions:figure_style"),
    (138, "Automatic caption generation", "text_to_gds.platform_extensions:generate_caption"),
    (139, "Device comparison table", "text_to_gds.platform_extensions:device_comparison_table"),
    (140, "Automatic benchmark reproduction", "text_to_gds.paper_benchmarks:run_paper_benchmark_suite"),
    (141, "Paper parameter extraction", "text_to_gds.platform_extensions:extract_literature_parameters"),
    (142, "DOI-linked benchmark database", "text_to_gds.platform_extensions:doi_benchmark_record"),
    (143, "Citation graph", "text_to_gds.platform_extensions:citation_graph"),
    (144, "Plugin architecture", "text_to_gds.platform_extensions:plugin_manifest"),
    (145, "Docker environment", "text_to_gds.platform_extensions:docker_environment"),
    (146, "Cloud simulation worker", "text_to_gds.platform_extensions:cloud_worker_job", "prepared_adapter"),
    (147, "REST API backend", "text_to_gds.platform_extensions:rest_api_spec"),
    (148, "Web dashboard", "text_to_gds.ui:serve_workbench"),
    (149, "Collaborative design workspace", "text_to_gds.platform_extensions:collaborative_workspace_event"),
    (150, "Permission system", "text_to_gds.platform_extensions:authorize"),
    (151, "CI/CD simulation testing", "text_to_gds.platform_extensions:ci_pipeline"),
    (152, "Automatic regression tests", "text_to_gds.platform_extensions:regression_test_case"),
    (153, "Device benchmark tests", "text_to_gds.platform_extensions:benchmark_test_case"),
    (154, "Documentation generator", "text_to_gds.platform_extensions:generate_api_documentation"),
    (155, "Example gallery", "text_to_gds.platform_extensions:example_gallery"),
    (156, "Tutorial notebooks", "text_to_gds.platform_extensions:tutorial_notebook"),
    (157, "Complete closed loop", "text_to_gds.platform_extensions:closed_loop_platform"),
]


IMPROVEMENTS = {
    row[0]: Improvement(row[0], row[1], row[2], row[3] if len(row) > 3 else "implemented")
    for row in _ROWS
}


def list_improvements() -> dict[str, Any]:
    return {
        "schema": "text-to-gds.improvement-registry.v1",
        "count": len(IMPROVEMENTS),
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
