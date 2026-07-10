"""Callable registry for all 146 capabilities in the Next Improvement List."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import import_module
from typing import Any


@dataclass(frozen=True)
class NextImprovement:
    id: int
    name: str
    implementation: str
    level: str = "implemented"

    def resolve(self) -> Any:
        module, attribute = self.implementation.split(":", 1)
        return getattr(import_module(module), attribute)


_ROWS = [
    (1, "External PCell plugin marketplace", "textlayout._legacy.foundry_extensions:PCellMarketplace"),
    (2, "Community device library", "textlayout._legacy.foundry_extensions:community_device_library"),
    (3, "Git-style device version control", "textlayout._legacy.verification:commit_device_version"),
    (4, "GDS geometry/frequency/performance diff", "textlayout._legacy.verification:chip_version_diff"),
    (5, "Experiment notebook generation", "textlayout._legacy.foundry_extensions:generate_experiment_notebook"),
    (6, "Project template generator", "textlayout._legacy.foundry_extensions:generate_project_template"),
    (7, "Microwave routing engine", "textlayout._legacy.layout_automation:route_microwave"),
    (8, "CPW auto-router", "textlayout._legacy.layout_automation:route_cpw"),
    (9, "Impedance-controlled routing", "textlayout._legacy.layout_automation:route_cpw"),
    (10, "Ground-plane optimizer", "textlayout._legacy.layout_automation:optimize_ground_plane"),
    (11, "Airbridge generator", "textlayout._legacy.layout_automation:airbridge_generator"),
    (12, "Crossover generator", "textlayout._legacy.layout_automation:crossover_generator"),
    (13, "Wirebond-pad optimizer", "textlayout._legacy.layout_automation:optimize_wirebond_pads"),
    (14, "Package-aware placement", "textlayout._legacy.layout_automation:package_aware_placement"),
    (15, "Automatic chip floorplanning", "textlayout._legacy.layout_automation:floorplan_chip"),
    (16, "Hierarchical layout", "textlayout._legacy.layout_automation:hierarchical_layout"),
    (17, "Parameterized-cell inheritance", "textlayout._legacy.layout_automation:inherit_cell_parameters"),
    (18, "Reusable quantum-cell library", "textlayout._legacy.layout_automation:quantum_cell_library"),
    (19, "Automatic labels", "textlayout._legacy.layout_automation:generate_layout_labels"),
    (20, "SEM alignment-marker library", "textlayout._legacy.layout_automation:sem_alignment_mark"),
    (21, "Foundry PDK import", "textlayout._legacy.foundry_extensions:import_foundry_pdk"),
    (22, "Process migration", "textlayout._legacy.foundry_extensions:migrate_process_geometry"),
    (23, "Fabrication cost estimator", "textlayout._legacy.foundry_extensions:estimate_fabrication_cost"),
    (24, "Fabrication schedule tracker", "textlayout._legacy.foundry_extensions:fabrication_schedule"),
    (25, "Wafer database dashboard", "textlayout._legacy.foundry_extensions:wafer_dashboard_data"),
    (26, "Chip inventory", "textlayout._legacy.foundry_extensions:record_chip_inventory"),
    (27, "Fabrication anomaly detection", "textlayout._legacy.foundry_extensions:detect_fabrication_anomalies"),
    (28, "Process-drift prediction", "textlayout._legacy.foundry_extensions:predict_process_drift"),
    (29, "Fabrication-recipe optimizer", "textlayout._legacy.foundry_extensions:optimize_fabrication_recipe"),
    (30, "Fabrication report", "textlayout._legacy.foundry_extensions:fabrication_report"),
    (31, "Ambegaokar-Baratoff model", "textlayout._legacy.junction_physics:ambegaokar_baratoff"),
    (32, "Temperature-dependent Ic", "textlayout._legacy.junction_physics:temperature_dependent_ic"),
    (33, "JJ aging", "textlayout._legacy.junction_physics:junction_aging"),
    (34, "Oxide-barrier tunneling", "textlayout._legacy.junction_physics:oxide_tunneling"),
    (35, "Junction-capacitance extraction", "textlayout._legacy.junction_physics:junction_capacitance"),
    (36, "Subgap leakage", "textlayout._legacy.junction_physics:subgap_leakage"),
    (37, "Quasiparticle loss", "textlayout._legacy.junction_physics:quasiparticle_loss"),
    (38, "TLS loss", "textlayout._legacy.junction_physics:tls_loss"),
    (39, "Magnetic-field JJ degradation", "textlayout._legacy.junction_physics:magnetic_junction_degradation"),
    (40, "Junction reliability", "textlayout._legacy.junction_physics:junction_reliability"),
    (41, "Automatic port placement", "textlayout._legacy.research_automation:automatic_port_placement"),
    (42, "Boundary-condition selection", "textlayout._legacy.research_automation:select_boundary_conditions"),
    (43, "Radiation-box sizing", "textlayout._legacy.research_automation:size_radiation_box"),
    (44, "Mesh-quality scoring", "textlayout._legacy.research_automation:mesh_quality_score"),
    (45, "Convergence AI checker", "textlayout._legacy.research_automation:convergence_checker"),
    (46, "Simulation-cost estimator", "textlayout._legacy.research_automation:estimate_simulation_cost"),
    (47, "Multi-solver comparison report", "textlayout._legacy.research_automation:multi_solver_report"),
    (48, "EM uncertainty estimation", "textlayout._legacy.em_extensions:em_error_estimate"),
    (49, "EM surrogate model", "textlayout._legacy.research_automation:train_em_surrogate"),
    (50, "Instant EM predictor", "textlayout._legacy.research_automation:predict_em_surrogate"),
    (51, "Topology recognition", "textlayout._legacy.research_automation:recognize_circuit_topology"),
    (52, "GDS circuit graph", "textlayout._legacy.research_automation:circuit_graph_features"),
    (53, "Parasitic-aware netlist", "textlayout._legacy.research_automation:parasitic_aware_netlist"),
    (54, "Distributed-circuit extraction", "textlayout._legacy.research_automation:extract_distributed_circuit"),
    (55, "Microwave-network synthesis", "textlayout._legacy.research_automation:synthesize_matching_network"),
    (56, "Filter synthesis", "textlayout._legacy.research_automation:synthesize_filter"),
    (57, "Impedance-matching synthesis", "textlayout._legacy.research_automation:synthesize_matching_network"),
    (58, "Transformer synthesis", "textlayout._legacy.research_automation:synthesize_transformer"),
    (59, "Matching-network optimizer", "textlayout._legacy.research_automation:optimize_smith_chart"),
    (60, "Smith-chart optimization", "textlayout._legacy.research_automation:optimize_smith_chart"),
    (61, "Gain-ripple prediction", "textlayout._legacy.nonlinear_extensions:gain_ripple_analysis"),
    (62, "Standing-wave analysis", "textlayout._legacy.nonlinear_extensions:standing_wave_effect"),
    (63, "Impedance-environment model", "textlayout._legacy.nonlinear_extensions:impedance_mismatch_analysis"),
    (64, "Pump-leakage simulation", "textlayout._legacy.nonlinear_extensions:pump_leakage"),
    (65, "Pump-cancellation optimizer", "textlayout._legacy.nonlinear_extensions:pump_cancellation_design"),
    (66, "Pump-heating model", "textlayout._legacy.research_automation:pump_heating"),
    (67, "Pump-induced frequency shift", "textlayout._legacy.research_automation:pump_induced_shift"),
    (68, "Stark-shift simulation", "textlayout._legacy.research_automation:pump_induced_shift"),
    (69, "Nonlinear Kerr extraction", "textlayout._legacy.research_automation:extract_kerr"),
    (70, "Bifurcation-boundary finder", "textlayout._legacy.research_automation:bifurcation_boundary"),
    (71, "Gain-stability map", "textlayout._legacy.nonlinear_extensions:stability_map"),
    (72, "Flux-noise sensitivity", "textlayout._legacy.research_automation:parameter_sensitivity"),
    (73, "Phase-noise sensitivity", "textlayout._legacy.research_automation:parameter_sensitivity"),
    (74, "Saturation-mechanism analysis", "textlayout._legacy.research_automation:saturation_mechanism_analysis"),
    (75, "Dynamic-range optimizer", "textlayout._legacy.nonlinear_extensions:optimize_dynamic_range"),
    (76, "Automatic TWPA unit-cell design", "textlayout._legacy.research_automation:design_twpa_unit_cell"),
    (77, "TWPA dispersion engineering", "textlayout._legacy.jtwpa:jtwpa_bloch_wavenumber"),
    (78, "TWPA phase matching", "textlayout._legacy.nonlinear_extensions:phase_matching_optimizer"),
    (79, "Artificial transmission-line synthesis", "textlayout._legacy.research_automation:artificial_transmission_line"),
    (80, "Photonic-crystal generator", "textlayout._legacy.research_automation:photonic_crystal_profile"),
    (81, "Stopband optimizer", "textlayout._legacy.research_automation:optimize_stopband"),
    (82, "Pump-depletion simulation", "textlayout._legacy.nonlinear_extensions:pump_depletion_model"),
    (83, "Four-wave mixing solver", "textlayout._legacy.theory.four_wave_mixing:four_wave_mixing_gain"),
    (84, "Three-wave mixing solver", "textlayout._legacy.theory.three_wave_mixing:three_wave_mixing_gain"),
    (85, "Broadband-gain optimizer", "textlayout._legacy.research_automation:optimize_broadband_gain"),
    (86, "Master-equation simulation", "textlayout._legacy.research_automation:lindblad_evolution"),
    (87, "Lindblad solver", "textlayout._legacy.research_automation:lindblad_evolution"),
    (88, "QuTiP backend", "textlayout._legacy.research_automation:qutip_backend"),
    (89, "Decoherence model", "textlayout._legacy.research_automation:decoherence_model"),
    (90, "Relaxation prediction", "textlayout._legacy.quantum_extensions:qubit_lifetime_prediction"),
    (91, "Dephasing prediction", "textlayout._legacy.research_automation:decoherence_model"),
    (92, "Thermal-photon analysis", "textlayout._legacy.research_automation:thermal_photon_analysis"),
    (93, "Quantum-noise propagation", "textlayout._legacy.research_automation:propagate_quantum_noise"),
    (94, "Squeezing tomography", "textlayout._legacy.research_automation:squeezing_tomography"),
    (95, "Quantum-state reconstruction", "textlayout._legacy.research_automation:reconstruct_quantum_state"),
    (96, "Cooldown tracking", "textlayout._legacy.research_automation:cooldown_tracking"),
    (97, "Fridge monitoring", "textlayout._legacy.research_automation:fridge_monitor"),
    (98, "Experiment scheduler", "textlayout._legacy.research_automation:schedule_experiments"),
    (99, "Overnight measurement agent", "textlayout._legacy.research_automation:overnight_agent"),
    (100, "Automatic parameter search", "textlayout._legacy.research_automation:automatic_parameter_search"),
    (101, "Reinforcement-learning tuning", "textlayout._legacy.platform_extensions:reinforcement_learning_optimizer"),
    (102, "Measurement anomaly detection", "textlayout._legacy.research_automation:measurement_anomaly_detection"),
    (103, "Measurement stop conditions", "textlayout._legacy.research_automation:measurement_stop_condition"),
    (104, "Instrument-health monitoring", "textlayout._legacy.research_automation:instrument_health"),
    (105, "Remote experiment control", "textlayout._legacy.research_automation:remote_experiment_command", "prepared_adapter"),
    (106, "ML-ready device database", "textlayout._legacy.delivery_extensions:ml_ready_device_record"),
    (107, "Circuit graph database", "textlayout._legacy.delivery_extensions:circuit_graph_database_record"),
    (108, "Paper vector database", "textlayout._legacy.platform_extensions:index_record"),
    (109, "Measurement similarity search", "textlayout._legacy.platform_extensions:similarity_search"),
    (110, "Failed-experiment database", "textlayout._legacy.delivery_extensions:failed_experiment_record"),
    (111, "Automatic metadata extraction", "textlayout._legacy.delivery_extensions:extract_metadata"),
    (112, "FAIR research-data export", "textlayout._legacy.delivery_extensions:fair_data_export"),
    (113, "DOI dataset generation", "textlayout._legacy.delivery_extensions:doi_dataset"),
    (114, "Paper-reading agent", "textlayout._legacy.research_automation:paper_reading_agent"),
    (115, "Equation-extraction agent", "textlayout._legacy.research_automation:equation_extraction_agent"),
    (116, "Simulation-reproduction agent", "textlayout._legacy.research_automation:simulation_reproduction_agent"),
    (117, "Reviewer-criticism agent", "textlayout._legacy.research_automation:reviewer_criticism_agent"),
    (118, "Experiment-planning agent", "textlayout._legacy.research_automation:experiment_planning_agent"),
    (119, "Hypothesis generator", "textlayout._legacy.research_automation:hypothesis_generator"),
    (120, "Research roadmap", "textlayout._legacy.research_automation:research_roadmap"),
    (121, "Autonomous design loop", "textlayout._legacy.research_automation:autonomous_research_loop"),
    (122, "Self-improving experiment model", "textlayout._legacy.research_automation:update_model_from_experiments"),
    (123, "LaTeX paper generator", "textlayout._legacy.delivery_extensions:latex_paper"),
    (124, "Overleaf export", "textlayout._legacy.delivery_extensions:overleaf_export"),
    (125, "Nature template", "textlayout._legacy.delivery_extensions:publication_template"),
    (126, "IEEE TAS template", "textlayout._legacy.delivery_extensions:publication_template"),
    (127, "Figure beautifier", "textlayout._legacy.delivery_extensions:beautify_figure"),
    (128, "Supplementary-information generator", "textlayout._legacy.delivery_extensions:supplementary_information"),
    (129, "Benchmark comparison table", "textlayout._legacy.delivery_extensions:benchmark_comparison_table"),
    (130, "Reviewer-response generator", "textlayout._legacy.delivery_extensions:reviewer_response"),
    (131, "Docker images", "textlayout._legacy.platform_extensions:docker_environment"),
    (132, "Kubernetes simulation workers", "textlayout._legacy.delivery_extensions:kubernetes_worker_manifest", "prepared_adapter"),
    (133, "Cloud GPU/HPC execution", "textlayout._legacy.delivery_extensions:hpc_job_script", "prepared_adapter"),
    (134, "Job queue", "textlayout._legacy.delivery_extensions:enqueue_job"),
    (135, "Simulation cache", "textlayout._legacy.em_extensions:cache_em_result"),
    (136, "Database backend", "textlayout._legacy.delivery_extensions:database_backend"),
    (137, "Authentication", "textlayout._legacy.delivery_extensions:create_password_record"),
    (138, "Collaborative web editor", "textlayout._legacy.delivery_extensions:collaborative_edit"),
    (139, "REST API", "textlayout._legacy.platform_extensions:rest_api_spec"),
    (140, "Python SDK", "textlayout._legacy.delivery_extensions:python_sdk_source"),
    (141, "Julia SDK", "textlayout._legacy.delivery_extensions:julia_sdk_source"),
    (142, "VS Code extension", "textlayout._legacy.delivery_extensions:vscode_extension_manifest"),
    (143, "CLI assistant", "textlayout._legacy.delivery_extensions:cli_assistant_commands"),
    (144, "Automated documentation", "textlayout._legacy.platform_extensions:generate_api_documentation"),
    (145, "Continuous benchmark testing", "textlayout._legacy.delivery_extensions:continuous_benchmark_pipeline"),
    (146, "Complete autonomous research loop", "textlayout._legacy.research_automation:autonomous_research_loop"),
]


NEXT_IMPROVEMENTS = {
    row[0]: NextImprovement(row[0], row[1], row[2], row[3] if len(row) > 3 else "implemented")
    for row in _ROWS
}


def list_next_improvements() -> dict[str, Any]:
    return {"schema": "text-to-gds.next-improvement-registry.v1", "count": len(NEXT_IMPROVEMENTS), "unique_implementations": len({item.implementation for item in NEXT_IMPROVEMENTS.values()}), "features": [asdict(NEXT_IMPROVEMENTS[index]) for index in sorted(NEXT_IMPROVEMENTS)]}


def validate_next_improvement_registry() -> dict[str, Any]:
    missing = sorted(set(range(1, 147)) - NEXT_IMPROVEMENTS.keys())
    unresolved = []
    for feature in NEXT_IMPROVEMENTS.values():
        try:
            if not callable(feature.resolve()):
                unresolved.append({"id": feature.id, "error": "implementation is not callable"})
        except (ImportError, AttributeError, SyntaxError) as exc:
            unresolved.append({"id": feature.id, "error": str(exc)})
    return {"passed": not missing and not unresolved, "count": len(NEXT_IMPROVEMENTS), "missing": missing, "unresolved": unresolved}


def call_next_improvement(feature_id: int, **kwargs: Any) -> Any:
    if feature_id not in NEXT_IMPROVEMENTS:
        raise KeyError(f"Unknown next improvement {feature_id}")
    return NEXT_IMPROVEMENTS[feature_id].resolve()(**kwargs)
