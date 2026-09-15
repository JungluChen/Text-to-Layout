# Function and MCP catalog

**Document class: MANUAL_DOCUMENTATION.** Source inventory recorded on
2026-09-15 from repository baseline `c0df0aaa99cb2de5c4baf6be181b4f313772979e`.
Inventory is not execution certification. See [maturity evidence](function_maturity_matrix.md),
[requirements](../REQUIREMENTS.md), [Design.md](../Design.md) and the
[guidebook](guidebook/README.md).

## Product capability map

| Capability | Existing product entry point | MCP / GUI delivery requirement |
| --- | --- | --- |
| Environment and solvers | `textlayout doctor --json`; `GET /health` | Keep environment health distinct from per-solver readiness. |
| Prompt to design | `textlayout prompt`; `POST /layout/from-text` | Shared deterministic workflow behind future UI and modern MCP adapter. |
| Typed DSL generation | `textlayout generate`; `POST /layout/generate` | Same units, verification and artifacts across clients. |
| Research and assumptions | `POST /layout/research` | Display sources and model limits before executing a run. |
| Geometry verification | `textlayout verify`; `POST /layout/verify` | Display measured values, limits and evidence. |
| Preview and export | `POST /layout/preview`; `POST /layout/export` | Accessible geometry inspection and explicit output destination. |
| Simulation | `textlayout simulate`; `POST /layout/simulate` | Preserve preparation/execution/convergence distinctions. |
| Reports and benchmarks | `POST /layout/report`; `POST /layout/benchmark` | Show provenance, comparison criteria and artifact access. |
| Long jobs | `textlayout jobs start/status/cancel/collect/resume` | Reuse job IDs; web/MCP adapters and parity need validation. |
| EPR, yield, chip, measurement | Existing CLI command families | Present only supported operations with their actual scientific limits. |
| Typed electrical-goal design | `textlayout design`; `POST /layout/from-goal` | CLI/API locally verified on 2026-09-15; GUI and modern MCP adapters pending. |

The current product API and legacy MCP server are different adapters. This table
is a capability mapping, not a claim that every HTTP route has an identical MCP
method today. Modern MCP facade names/schemas must be specified and tested before
being advertised. Do not add implementation to the frozen legacy tree merely to
make feature counts match.

## Typed electrical-goal function

`textlayout design REQUIREMENTS.json --out DIRECTORY --no-solver` and
`POST /layout/from-goal` use the shared deterministic graph. The API body is
`{"requirements": {...}, "execute_solver": false}`; `output_dir` is optional.
CLI/API default to attempting solver execution unless explicitly disabled.

| Input | Contract |
| --- | --- |
| `quantity` | Required: `capacitance_pf`, `inductance_nh`, `impedance_ohm`, or `quarter_wave_frequency_ghz`. |
| `value` | Required positive finite number in the units encoded by `quantity`. |
| `technology` | Default `generic_2metal`; must name an available technology. |
| `operating_frequency_ghz` | Optional positive context frequency; must equal a quarter-wave frequency target when both are supplied. It is not bandwidth qualification. |
| `min_width_um`, `min_gap_um` | Optional positive limits; cannot weaken the technology rules. |
| `max_bbox_width_um`, `max_bbox_height_um` | Optional positive footprint limits in micrometres. |
| `tolerance_percent` | Positive target-error limit; default 5%. |

Unknown fields and invalid numbers are rejected. Unreachable bounded searches
fail with a feasibility record. The operation writes geometry, research,
verification and review files to the output directory; optional extraction
requires an installed solver. `requirements_verification.json`,
`verification.json`, `design_review.json` and `report.md` share the final target
verdict. Read `target_basis` and simulation status before interpreting a pass.
CLI exit 1 indicates a rejected/failed design; `--require-simulation` returns
2 when a passing design lacks the required physics evidence. See the
[verified command and AI example](guidebook/README.md#design-from-an-electrical-goal).
No MCP method for this modern function is advertised until its adapter exists.

## Current MCP source inventory

The `text-to-gds` entry point resolves through `src/text_to_gds/server.py` to
`src/textlayout/_legacy/server.py`. Static inspection found **95 decorated MCP
tool functions**. They are compatibility inventory; registration at runtime,
dependency availability, numerical correctness and host behavior were not tested
by this inventory. Descriptions below are source docstrings, not verified claims.
In particular, historical claims such as “analog”, “validated”, or function
counts inside docstrings do not establish supported commercial parity or maturity.

For the installed release, the authoritative invocation contract is MCP
`tools/list` after initialization; use `tools/call` for an operation. Python
signatures below aid navigation but do not replace the runtime JSON Schema.
Optional backends may fail or be unavailable. Broad dispatcher tools may write
files or run solvers; discovery alone must not execute them.

| Tool | Python inputs (defaults included) | Python return annotation | Source description (unverified) |
| --- | --- | --- | --- |
| [`compile_layout`](../src/textlayout/_legacy/server.py#L226) | `pcell: str='manhattan_josephson_junction', parameters: dict[str, Any] \| None=None, output_name: str='layout.gds', layout_quality_mode: str=DEFAULT_LAYOUT_QUALITY_MODE, design_intent_path: str \| None=None` | `dict[str, Any]` | Compile a registered superconducting PCell into GDS and a semantic sidecar. |
| [`list_professional_backends`](../src/textlayout/_legacy/server.py#L294) | `(none)` | `list[dict[str, object]]` | List professional EDA/simulation backends and their local availability. |
| [`run_backend_operation`](../src/textlayout/_legacy/server.py#L300) | `backend_name: str, operation: str, request: dict[str, Any] \| None=None, output_name: str='backend_run'` | `dict[str, Any]` | Run a universal backend operation: generate, simulate, or extract. |
| [`run_drc`](../src/textlayout/_legacy/server.py#L319) | `gds_path: str, ruleset: str='builtin_min_bbox_width', min_width_um: float=0.1` | `dict[str, Any]` | Run a local KLayout-backed min-width pass and emit a JSON DRC report. |
| [`run_process_drc`](../src/textlayout/_legacy/server.py#L364) | `gds_path: str, deck_path: str='drc/superconducting_min_width.drc', output_name: str \| None=None, klayout_executable: str='klayout'` | `dict[str, Any]` | Run an external headless KLayout DRC deck and normalize its report. |
| [`list_pcells`](../src/textlayout/_legacy/server.py#L437) | `(none)` | `dict[str, Any]` | List registered PCells and the active process-stack defaults. |
| [`extract_layout`](../src/textlayout/_legacy/server.py#L452) | `sidecar_path: str, include_gds_shapes: bool=True, jc_ua_per_um2: float \| None=None, specific_capacitance_ff_per_um2: float \| None=None` | `dict[str, Any]` | Summarize performance-relevant parameters from a sidecar and optional GDS scan. |
| [`extract_physics_graph_artifact`](../src/textlayout/_legacy/server.py#L517) | `sidecar_path: str, output_name: str \| None=None, jc_ua_per_um2: float \| None=None, specific_capacitance_ff_per_um2: float \| None=None` | `dict[str, Any]` | Extract the physics_graph.json compiler IR from a layout sidecar. |
| [`generate_solver_inputs_from_physics_graph`](../src/textlayout/_legacy/server.py#L538) | `physics_graph_path: str, output_name: str='solver_inputs'` | `dict[str, Any]` | Generate openEMS, Elmer, and Palace input files from physics_graph.json. |
| [`generate_josephsoncircuits_model_from_physics_graph`](../src/textlayout/_legacy/server.py#L549) | `physics_graph_path: str, output_name: str='josephsoncircuits_model.json'` | `dict[str, Any]` | Generate a JosephsonCircuits-ready model list from physics_graph.json. |
| [`run_inverse_design_jpa`](../src/textlayout/_legacy/server.py#L564) | `prompt: str, output_name: str='inverse_jpa', iterations: int=5, algorithm: str='cma-es'` | `dict[str, Any]` | Run gradient-free inverse design where every candidate regenerates GDS. |
| [`compare_measurement_engine`](../src/textlayout/_legacy/server.py#L576) | `measurement_path: str, simulation_path: str \| None=None, output_name: str='measurement_comparison.json', fit_kind: str='auto'` | `dict[str, Any]` | Fit measurement data and compare it with a simulation result artifact. |
| [`run_axion_search_jpa_final_test`](../src/textlayout/_legacy/server.py#L596) | `output_name: str='axion_jpa'` | `dict[str, Any]` | Run the final flux-tunable JPA compiler test from the user request. |
| [`run_magic_extract`](../src/textlayout/_legacy/server.py#L603) | `gds_path: str, output_name: str \| None=None, top_cell: str \| None=None, tech_file: str \| None=None, magic_executable: str='magic'` | `dict[str, Any]` | Run Magic VLSI GDS import/extraction/SPICE export when Magic is available. |
| [`list_simulators`](../src/textlayout/_legacy/server.py#L646) | `(none)` | `dict[str, Any]` | List local external simulator adapters and installation hints. |
| [`list_research_integrations`](../src/textlayout/_legacy/server.py#L655) | `(none)` | `dict[str, Any]` | List optional upstream research integrations and their local availability. |
| [`list_fabrication_processes`](../src/textlayout/_legacy/server.py#L664) | `(none)` | `dict[str, Any]` | List local measured fabrication-process records. |
| [`list_process_design_kits`](../src/textlayout/_legacy/server.py#L674) | `(none)` | `dict[str, Any]` | List validated, versioned superconducting PDKs available to local workflows. |
| [`inspect_process_design_kit`](../src/textlayout/_legacy/server.py#L684) | `process_id: str, version: str \| None=None, material: str \| None=None, frequency_ghz: float=6.0` | `dict[str, Any]` | Resolve a PDK version and optionally calculate one material's surface impedance. |
| [`list_improvement_functions`](../src/textlayout/_legacy/server.py#L706) | `(none)` | `dict[str, Any]` | List and validate all 157 improvement-list implementations. |
| [`run_improvement_function`](../src/textlayout/_legacy/server.py#L714) | `feature_id: int, arguments: dict[str, Any] \| None=None` | `Any` | Execute one registered improvement function with JSON-compatible arguments. |
| [`list_next_improvement_functions`](../src/textlayout/_legacy/server.py#L722) | `(none)` | `dict[str, Any]` | List and import-validate all 146 functions in the Next Improvement List. |
| [`run_next_improvement_function`](../src/textlayout/_legacy/server.py#L730) | `feature_id: int, arguments: dict[str, Any] \| None=None` | `Any` | Execute one next-list function with JSON-compatible arguments. |
| [`list_third_wave_improvement_functions`](../src/textlayout/_legacy/server.py#L738) | `(none)` | `dict[str, Any]` | List and import-validate all 37 third-wave autonomous-scientist functions. |
| [`run_third_wave_improvement_function`](../src/textlayout/_legacy/server.py#L746) | `feature_id: int, arguments: dict[str, Any] \| None=None` | `Any` | Execute one third-wave function with JSON-compatible arguments. |
| [`extract_equivalent_circuit`](../src/textlayout/_legacy/server.py#L754) | `sidecar_path: str, output_name: str \| None=None` | `dict[str, Any]` | Extract a circuit from GDS polygons or a sidecar, then generate SPICE and Julia. |
| [`run_lvs`](../src/textlayout/_legacy/server.py#L782) | `extracted_circuit_path: str, schematic_path: str` | `dict[str, Any]` | Run superconducting LVS against a JSON or SPICE schematic. |
| [`generate_wafer_level_mask`](../src/textlayout/_legacy/server.py#L794) | `chip_gds: str, output_name: str='wafer.gds', wafer_diameter_mm: float=50.8, chip_width_mm: float=5.0, chip_height_mm: float=5.0, dicing_lane_um: float=100.0, edge_exclusion_mm: float=2.0` | `dict[str, Any]` | Generate a wafer GDS containing chip placements, dicing lanes, and alignment marks. |
| [`plan_process_aware_jpa`](../src/textlayout/_legacy/server.py#L816) | `prompt: str, nominal_junction_area_um2: float=0.0484` | `dict[str, Any]` | Correct a JPA design using a named process record and report expected Ic yield. |
| [`run_uncertainty_analysis`](../src/textlayout/_legacy/server.py#L829) | `process_name: str='NCU 2025 AlOx process', output_name: str='jpa-process-yield', samples: int=5000, seed: int=42, junction_area_um2: float=0.0484, target_frequency_ghz: float=6.0, target_gain_db: float=20.0` | `dict[str, Any]` | Run process/lithography/capacitance Monte Carlo and write a yield report. |
| [`analyze_cryostat_input_chain`](../src/textlayout/_legacy/server.py#L855) | `chain_path: str \| None=None, source_temperature_k: float=300.0` | `dict[str, Any]` | Calculate cryogenic chain Friis noise, pump power, and JPA headroom. |
| [`plan_ljpa`](../src/textlayout/_legacy/server.py#L865) | `prompt: str` | `dict[str, Any]` | Convert an LJPA prompt into clarification questions and a local design workflow. |
| [`export_3d_preview`](../src/textlayout/_legacy/server.py#L887) | `gds_path: str, output_name: str \| None=None` | `dict[str, Any]` | Export a local 2.5D HTML/JSON process-stack preview from GDS layer boxes. |
| [`export_cad_artifacts`](../src/textlayout/_legacy/server.py#L897) | `gds_path: str, output_name: str \| None=None` | `dict[str, Any]` | Export SVG/DXF/STL/GLB CAD-style inspection artifacts from a GDS layout. |
| [`export_scientific_plot`](../src/textlayout/_legacy/server.py#L912) | `simulation_path: str, output_name: str \| None=None, title: str \| None=None` | `dict[str, Any]` | Export publication-style PNG/SVG/CSV/JSON plot artifacts from simulation JSON. |
| [`export_rf_network`](../src/textlayout/_legacy/server.py#L931) | `simulation_path: str, output_name: str \| None=None, reference_ohm: float=50.0` | `dict[str, Any]` | Export simulation data as Touchstone S2P, RF plot, CSV, and JSON report. |
| [`export_mesh`](../src/textlayout/_legacy/server.py#L951) | `gds_path: str, sidecar_path: str \| None=None, process_path: str \| None=None, output_name: str \| None=None, mesh_size_um: float \| None=None` | `dict[str, Any]` | Mesh the GDS-on-process-stack geometry with gmsh into a 3D .msh for Palace/Elmer. |
| [`export_palace_project`](../src/textlayout/_legacy/server.py#L992) | `gds_path: str, sidecar_path: str \| None=None, process_path: str \| None=None, output_name: str \| None=None, problem_type: str='Eigenmode', target_frequency_ghz: float=6.0, num_modes: int=4, run: bool=False` | `dict[str, Any]` | Generate a Palace eigenmode/driven project (config + gmsh mesh); the HFSS-eigenmode analog. |
| [`export_elmer_project`](../src/textlayout/_legacy/server.py#L1022) | `gds_path: str, sidecar_path: str \| None=None, process_path: str \| None=None, output_name: str \| None=None, run: bool=False` | `dict[str, Any]` | Generate an Elmer electrostatic capacitance project (mesh + .sif); the Q3D analog. |
| [`export_fasthenry`](../src/textlayout/_legacy/server.py#L1046) | `gds_path: str, sidecar_path: str \| None=None, process_path: str \| None=None, output_name: str \| None=None, run: bool=True` | `dict[str, Any]` | Generate (and run when installed) a FastHenry conductor-inductance extraction deck. |
| [`export_fastcap`](../src/textlayout/_legacy/server.py#L1068) | `gds_path: str, sidecar_path: str \| None=None, process_path: str \| None=None, output_name: str \| None=None, run: bool=True` | `dict[str, Any]` | Generate (and run when installed) a FastCap capacitance-matrix extraction deck. |
| [`list_em_solvers`](../src/textlayout/_legacy/server.py#L1090) | `(none)` | `dict[str, Any]` | List EM backends (openEMS, HFSS, Sonnet, Palace, Elmer) with method, license, availability. |
| [`recommend_em_solver`](../src/textlayout/_legacy/server.py#L1096) | `sidecar_path: str \| None=None, device_type: str \| None=None` | `dict[str, Any]` | Route a device to the best EM backend, open-first (commercial = validation-only). |
| [`route_open_solver`](../src/textlayout/_legacy/server.py#L1111) | `device: str, target_accuracy: str='iteration', validation: bool=False` | `dict[str, Any]` | Plan the open-source solver backends for a device (CPW/JPA/qubit/...). |
| [`cross_validate_solvers`](../src/textlayout/_legacy/server.py#L1125) | `sources: list[dict[str, Any]], quantity: str='value', tolerance_pct: float=5.0` | `dict[str, Any]` | Cross-check one quantity across >=2 solver/theory sources and score confidence. |
| [`export_open_eigenmode`](../src/textlayout/_legacy/server.py#L1140) | `gds_path: str, output_name: str \| None=None, sidecar_path: str \| None=None, process_path: str \| None=None, target_frequency_ghz: float=6.0, run: bool=False` | `dict[str, Any]` | Open HFSS-eigenmode analog (gmsh -> Palace) in the HFSS schema (f0/Q/participation). |
| [`extract_open_q3d`](../src/textlayout/_legacy/server.py#L1162) | `gds_path: str, output_name: str \| None=None, sidecar_path: str \| None=None, process_path: str \| None=None, run: bool=False` | `dict[str, Any]` | Open Q3D analog: C matrix (Elmer/FastCap) + L (FastHenry) + coupling. |
| [`tune_idc_capacitance`](../src/textlayout/_legacy/server.py#L1182) | `target_pf: float, epsilon_r: float=11.45, min_feature_um: float=0.2, tolerance_pct: float=1.0` | `dict[str, Any]` | Auto-tune interdigital-capacitor finger geometry to hit a target capacitance. |
| [`export_superconducting_material`](../src/textlayout/_legacy/server.py#L1198) | `material: str='Nb', thickness_nm: float=100.0, tc_k: float \| None=None, lambda_l_nm: float \| None=None, rn_sheet_ohm: float \| None=None, trace_width_um: float \| None=None, trace_length_um: float \| None=None, geometric_inductance_ph: float \| None=None, output_name: str \| None=None` | `dict[str, Any]` | Model a superconducting film: sheet kinetic inductance, total Lk, participation. |
| [`export_package_model`](../src/textlayout/_legacy/server.py#L1231) | `operating_frequency_ghz: float=6.0, bondwire_length_um: float=800.0, bondwire_diameter_um: float=25.0, bondwire_count: int=1, bondwire_pitch_um: float \| None=None, package_width_mm: float=6.0, package_length_mm: float=6.0, package_height_mm: float=3.0, package_epsilon_r: float=1.0, coupling_capacitance_ff: float \| None=None, output_name: str \| None=None` | `dict[str, Any]` | Estimate chip/wirebond/package parasitics: bondwire L, package modes, warnings. |
| [`fit_measurement`](../src/textlayout/_legacy/server.py#L1263) | `data_path: str, fit_kind: str='auto', output_name: str \| None=None, device_id: str \| None=None, process_id: str \| None=None, target_frequency_ghz: float \| None=None, database_name: str='experiments.sqlite'` | `dict[str, Any]` | Fit a resonator/JPA-gain/pump/noise trace (CSV or JSON) into device metrics. |
| [`export_openems_project`](../src/textlayout/_legacy/server.py#L1303) | `sidecar_path: str, output_name: str \| None=None, target_frequency_ghz: float \| None=None, run: bool=True` | `dict[str, Any]` | Generate and (when openEMS is installed and run=True) execute a real CPW EM extraction. |
| [`export_hfss_project`](../src/textlayout/_legacy/server.py#L1325) | `gds_path: str, sidecar_path: str \| None=None, process_path: str \| None=None, output_name: str \| None=None, setup_frequency_ghz: float=6.0` | `dict[str, Any]` | Write a process-mapped PyAEDT HFSS driven/eigenmode project script. |
| [`export_pyaedt_project`](../src/textlayout/_legacy/server.py#L1349) | `gds_path: str, sidecar_path: str \| None=None, process_path: str \| None=None, output_name: str \| None=None, setup_frequency_ghz: float=6.0, sweep_start_ghz: float=1.0, sweep_stop_ghz: float=12.0, sweep_points: int=221, run: bool=False, solve: bool=False` | `dict[str, Any]` | Build HFSS driven/eigenmode and Q3D PyAEDT scripts, optionally running AEDT. |
| [`export_q3d_extract`](../src/textlayout/_legacy/server.py#L1391) | `gds_path: str, sidecar_path: str \| None=None, process_path: str \| None=None, output_name: str \| None=None, setup_frequency_ghz: float=6.0, run: bool=False, solve: bool=False` | `dict[str, Any]` | Generate or run Q3D capacitance-matrix extraction from GDS and process data. |
| [`recommend_pyaedt_design_correction`](../src/textlayout/_legacy/server.py#L1431) | `target_frequency_ghz: float, extracted_frequency_ghz: float, extracted_impedance_ohm: float \| None=None, target_impedance_ohm: float=50.0` | `dict[str, Any]` | Convert HFSS/Q3D errors into first-order geometry seeds for Optuna. |
| [`run_pyaedt_design_iteration`](../src/textlayout/_legacy/server.py#L1447) | `sidecar_path: str, target_frequency_ghz: float, extracted_frequency_ghz: float, extracted_impedance_ohm: float \| None=None, target_impedance_ohm: float=50.0, output_name: str \| None=None` | `dict[str, Any]` | Apply one HFSS-derived correction to supported CPW/LJPA geometry and write new GDS. |
| [`run_pyaedt_benchmarks`](../src/textlayout/_legacy/server.py#L1516) | `results_root: str \| None=None, output_name: str='pyaedt-benchmark-suite'` | `dict[str, Any]` | Compare licensed HFSS/Q3D result JSON against solver qualification targets. |
| [`export_sonnet_project`](../src/textlayout/_legacy/server.py#L1531) | `gds_path: str, output_name: str \| None=None` | `dict[str, Any]` | Write a SonnetLab script and expected Sonnet project path from GDS. |
| [`export_measurement_plan`](../src/textlayout/_legacy/server.py#L1547) | `sidecar_path: str, simulation_path: str \| None=None, output_name: str \| None=None` | `dict[str, Any]` | Write a QCoDeS-style measurement plan and script without touching instruments. |
| [`export_measurement_recipe`](../src/textlayout/_legacy/server.py#L1571) | `recipe: str='gain_map', output_name: str \| None=None` | `dict[str, Any]` | Write an executable dry-run/QCoDeS-oriented JPA measurement recipe. |
| [`export_epr_analysis`](../src/textlayout/_legacy/server.py#L1587) | `sidecar_path: str, field_energy_path: str \| None=None, hfss_project_path: str \| None=None, output_name: str \| None=None` | `dict[str, Any]` | Write pyEPR HFSS analysis and optionally evaluate exported field energies. |
| [`export_hamiltonian_model`](../src/textlayout/_legacy/server.py#L1609) | `sidecar_path: str, output_name: str \| None=None, jc_ua_per_um2: float=1.0, capacitance_ff: float \| None=None, flux_bias_phi0: float=0.0, squid_asymmetry: float=0.0` | `dict[str, Any]` | Write a scqubits-ready Hamiltonian starter model from sidecar JJ/SQUID values. |
| [`export_quantum_metal_bridge`](../src/textlayout/_legacy/server.py#L1634) | `sidecar_path: str, output_name: str \| None=None` | `dict[str, Any]` | Write Quantum Metal/Qiskit Metal bridge metadata for component architecture mapping. |
| [`export_scientific_report`](../src/textlayout/_legacy/server.py#L1651) | `sidecar_path: str, gds_layout_png: str \| None=None, output_name: str \| None=None, jc_ua_per_um2: float=1.0, target_frequency_ghz: float \| None=None, target_bandwidth_mhz: float \| None=None, flux_bias_phi0: float=0.0, squid_asymmetry: float=0.05` | `dict[str, Any]` | Assemble the full ten-figure JPA scientific report (composite PNG/SVG + JSON manifest). |
| [`golden_compare`](../src/textlayout/_legacy/server.py#L1683) | `device: dict[str, Any] \| str, reference: dict[str, Any] \| str \| None=None` | `dict[str, Any]` | Compare generated/extracted device metadata against cited golden references. |
| [`run_analytical_verification`](../src/textlayout/_legacy/server.py#L1699) | `output_name: str='jpa-theory-verification', center_frequency_ghz: float=6.0, kappa_mhz: float=120.0, pump_coupling_mhz: float=55.0, simulation_path: str \| None=None, measurement_path: str \| None=None` | `dict[str, Any]` | Compare analytical Kerr-JPA metrics with optional simulation and measurement JSON. |
| [`record_experiment_feedback`](../src/textlayout/_legacy/server.py#L1727) | `device_id: str, design_path: str, measurement_path: str, process_id: str \| None=None, database_name: str='experiments.sqlite'` | `dict[str, Any]` | Record measured results and return correction factors for the next design. |
| [`export_jpa_analysis`](../src/textlayout/_legacy/server.py#L1747) | `sidecar_path: str, output_name: str \| None=None, jc_ua_per_um2: float=1.0, target_frequency_ghz: float \| None=None, target_bandwidth_mhz: float \| None=None, n_pump_points: int=16` | `dict[str, Any]` | Run a real JosephsonCircuits.jl pump sweep for gain/P1dB/noise/squeezing/stability. |
| [`run_traveling_wave_paper_benchmark`](../src/textlayout/_legacy/server.py#L1773) | `output_name: str='traveling-wave-paper-parity'` | `dict[str, Any]` | Reproduce the two bundled papers' linear bands and reduced traveling-wave gain. |
| [`run_gaydamachenko_jtwpa_benchmark`](../src/textlayout/_legacy/server.py#L1786) | `output_name: str='gaydamachenko-3wm-jtwpa', pump_frequency_ghz: float=12.92` | `dict[str, Any]` | Reproduce the arXiv:2209.11052v2 loaded 3WM-JTWPA reference design. |
| [`run_paper_benchmarks`](../src/textlayout/_legacy/server.py#L1802) | `output_name: str='paper-benchmark-suite'` | `dict[str, Any]` | Run every supported paper reproduction and explicitly skip missing backends. |
| [`run_research_optimization`](../src/textlayout/_legacy/server.py#L1814) | `sidecar_path: str, output_name: str \| None=None, n_trials: int=16, target_frequency_ghz: float=5.0, target_gain_db: float=20.0, target_bandwidth_mhz: float=500.0, min_p1db_dbm: float=-100.0, force_fallback: bool=False` | `dict[str, Any]` | Run Optuna if installed, else deterministic constrained surrogate optimization. |
| [`run_validation_checklist`](../src/textlayout/_legacy/server.py#L1863) | `gds_path: str \| None=None, sidecar_path: str \| None=None, drc_path: str \| None=None, extraction_path: str \| None=None, simulation_path: str \| None=None, cad_path: str \| None=None, em_path: str \| None=None, measurement_path: str \| None=None, output_name: str='validation.json'` | `dict[str, Any]` | Write an academic/industrial validation checklist plus a TRL readiness score. |
| [`run_parameter_sweep`](../src/textlayout/_legacy/server.py#L2043) | `sidecar_path: str, sweep_parameter: str='jc_ua_per_um2', start: float=0.5, stop: float=5.0, points: int=9, output_name: str \| None=None, jc_ua_per_um2: float=1.0, shunt_capacitance_ff: float=0.0, target_frequency_ghz: float \| None=None, target_gain_db: float=20.0, target_bandwidth_mhz: float \| None=None, pump_current_fraction: float=0.017, coupling_capacitance_ff: float \| None=None, resonator_capacitance_ff: float \| None=None, flux_bias_phi0: float=0.0, squid_asymmetry: float=0.0, flux_sweep_span_phi0: float=1.0, flux_sweep_points: int=101, flux_period_current_ma: float \| None=None, flux_mutual_inductance_ph: float \| None=None` | `dict[str, Any]` | Run a local layout-derived parameter sweep and write JSON/CSV/PNG/SVG artifacts. |
| [`run_design_workflow`](../src/textlayout/_legacy/server.py#L2116) | `prompt: str, output_name: str='ljpa_seed.gds', parameters: dict[str, Any] \| None=None, jc_ua_per_um2: float \| None=2.0, simulator: str='analytical_jj', analysis_mode: str='auto', pump_current_fraction: float=0.017, coupling_capacitance_ff: float \| None=None, resonator_capacitance_ff: float \| None=None, flux_bias_phi0: float=0.0, squid_asymmetry: float=0.0, flux_sweep_span_phi0: float=1.0, flux_sweep_points: int=101, flux_period_current_ma: float \| None=None, flux_mutual_inductance_ph: float \| None=None, substrate: str \| None=None, epsilon_r: float \| None=None, substrate_thickness_um: float \| None=None, ground_width_um: float \| None=None, package_clearance_um: float \| None=None, pump_frequency_ghz: float \| None=None, pump_power_dbm: float \| None=None, pump_mode: str \| None=None, impedance_tolerance_ohm: float=2.5, literature_comparison: dict[str, Any] \| None=None` | `dict[str, Any]` | Run a local prompt-to-layout workflow and write a browser workbench. |
| [`run_optimized_design_workflow`](../src/textlayout/_legacy/server.py#L2370) | `prompt: str, output_name: str='ljpa_optimized.gds', parameters: dict[str, Any] \| None=None, jc_ua_per_um2: float=2.0, max_iterations: int=4, simulator: str='analytical_jj', analysis_mode: str='auto', pump_current_fraction: float=0.017, coupling_capacitance_ff: float \| None=None, resonator_capacitance_ff: float \| None=None, flux_bias_phi0: float=0.0, squid_asymmetry: float=0.0, flux_sweep_span_phi0: float=1.0, flux_sweep_points: int=101, flux_period_current_ma: float \| None=None, flux_mutual_inductance_ph: float \| None=None, substrate: str \| None=None, epsilon_r: float \| None=None, substrate_thickness_um: float \| None=None, ground_width_um: float \| None=None, package_clearance_um: float \| None=None, pump_frequency_ghz: float \| None=None, pump_power_dbm: float \| None=None, pump_mode: str \| None=None, impedance_tolerance_ohm: float=8.0` | `dict[str, Any]` | Optimize first-pass LJPA geometry with a local surrogate, then run workflow. |
| [`run_simulation`](../src/textlayout/_legacy/server.py#L2466) | `sidecar_path: str, simulator: str='analytical_jj', jc_ua_per_um2: float=1.0, shunt_capacitance_ff: float=0.0, analysis_mode: str='auto', pump_current_fraction: float=0.017, coupling_capacitance_ff: float \| None=None, resonator_capacitance_ff: float \| None=None, adapter_executable: str \| None=None, target_frequency_ghz: float \| None=None, target_gain_db: float=20.0, target_bandwidth_mhz: float \| None=None, flux_bias_phi0: float=0.0, squid_asymmetry: float=0.0, flux_sweep_span_phi0: float=1.0, flux_sweep_points: int=101, flux_period_current_ma: float \| None=None, flux_mutual_inductance_ph: float \| None=None` | `dict[str, Any]` | Run ideal JJ simulation and optional local external simulator adapters. |
| [`record_quantum_device`](../src/textlayout/_legacy/server.py#L2626) | `device_id: str, gds_path: str='', status: str='draft', device_type: str='', process_id: str='', jc_ua_per_um2: float=0.0, paper_doi: str='', tags: list[str] \| None=None, geometry_json: str='{}', sidecar_json: str='{}'` | `dict[str, Any]` | Record a quantum device in the device database. |
| [`query_quantum_devices`](../src/textlayout/_legacy/server.py#L2695) | `device_type: str='', status: str='', process_id: str='', limit: int=50` | `dict[str, Any]` | Query the quantum device database with optional filters. |
| [`export_device_training_data`](../src/textlayout/_legacy/server.py#L2736) | `(none)` | `dict[str, Any]` | Export device database as (geometry, performance) training pairs. |
| [`check_physics_constraints`](../src/textlayout/_legacy/server.py#L2758) | `specs_json: str, device_id: str=''` | `dict[str, Any]` | Run physics constraint checks against a specification dict. |
| [`check_design_feasibility`](../src/textlayout/_legacy/server.py#L2777) | `device: str, targets_json: str, device_id: str=''` | `dict[str, Any]` | Pre-layout 'can this exist?' gate: ACCEPT/REJECT a spec before generating GDS. |
| [`list_physics_templates`](../src/textlayout/_legacy/server.py#L2793) | `(none)` | `dict[str, Any]` | List device physics templates (CPW, Resonator, JPA, JTWPA, SFQ, Transmon). |
| [`validate_device_template`](../src/textlayout/_legacy/server.py#L2799) | `sidecar_path: str, device: str` | `dict[str, Any]` | Check a layout sidecar against a device template's must-have feature list. |
| [`validate_layout_geometry`](../src/textlayout/_legacy/server.py#L2806) | `gds_path: str, sidecar_path: str \| None=None` | `dict[str, Any]` | Polygon-level GDS geometry validation. |
| [`review_layout`](../src/textlayout/_legacy/server.py#L2824) | `sidecar_path: str, simulation_path: str \| None=None, drc_path: str \| None=None, device: str \| None=None` | `dict[str, Any]` | Run the rule-based review committee on a layout's evidence. |
| [`evaluate_signoff_level`](../src/textlayout/_legacy/server.py#L2855) | `evidence_json: str` | `dict[str, Any]` | Evaluate Text-to-GDS signoff Level 0-6 from explicit evidence JSON. |
| [`understand_layout`](../src/textlayout/_legacy/server.py#L2862) | `gds_path: str, sidecar_path: str \| None=None` | `dict[str, Any]` | Parse a GDS into circuit elements and classify the device drawn. |
| [`run_open_benchmarks`](../src/textlayout/_legacy/server.py#L2872) | `(none)` | `dict[str, Any]` | Run the open functional benchmark suite (CPW Z0/f0, IDC 0.6 pF, JPA gain). |
| [`run_ai_scientist`](../src/textlayout/_legacy/server.py#L2878) | `prompt: str, device: str='JPA', targets_json: str \| None=None, output_name: str='ai_scientist.gds', jc_ua_per_um2: float=2.0` | `dict[str, Any]` | End-to-end open-source pipeline: feasibility -> generate -> review -> readiness. |
| [`predict_device_performance`](../src/textlayout/_legacy/server.py#L2952) | `source_path: str, device_id: str=''` | `dict[str, Any]` | Predict EM performance from GDS or sidecar using the layout transformer. |
| [`score_layout_quality`](../src/textlayout/_legacy/server.py#L2975) | `sidecar_json: str='{}', drc_json: str='{}', target_specs_json: str='{}'` | `dict[str, Any]` | Score a quantum device layout on fabrication, design, and performance. |
| [`tokenize_layout`](../src/textlayout/_legacy/server.py#L3000) | `source_path: str, max_tokens: int=2048` | `dict[str, Any]` | Tokenize a GDS or sidecar into ML-ready token sequences. |
| [`list_quantum_devices`](../src/textlayout/_legacy/server.py#L3028) | `(none)` | `dict[str, Any]` | List all devices in the quantum device database with summary stats. |

## Catalog requirements for each release

For every user-facing function, record a stable capability ID and display name,
purpose, current status/maturity and evidence, CLI syntax, HTTP method/path and
actual MCP tool name. Include input JSON Schema, units, constraints/defaults,
output schema/artifacts, required solver/version, execution location, side
effects, expected errors, runnable CLI/MCP examples and an AI prompt. Mark absent
adapters explicitly pending. Runtime availability and scientific maturity are
separate fields; neither may be inferred from the existence of a function.

Build the searchable Functions UI and published reference from the same
versioned registry. Add `tools/list` and OpenAPI comparison checks to prevent
catalog drift when adapters change. Keep legacy names documented until their
migration and compatibility policy are implemented. Generated plugin bundles
must be refreshed through `scripts/bundle_plugin.py`, not hand-edited.

Before publishing a release, verify all advertised names against live discovery,
validate example arguments against returned schemas, execute bounded discovery
and geometry examples on both Codex and Claude Code, and retain explicit
missing-solver and invalid-input results. Large dispatcher registries need their
own expanded inventory before being advertised as individually tested functions.
