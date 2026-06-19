# MCP Tool Contract

## `compile_layout`

Inputs:

- `pcell`: registered PCell name.
- `parameters`: JSON object passed to the PCell.
- `output_name`: artifact filename.

Output includes `status`, `gds_path`, `screenshot_path`, and `sidecar_path`.

## `run_drc`

Inputs:

- `gds_path`
- `ruleset`
- `min_width_um`

Output uses schema `text-to-gds.drc.v0` and includes `engine`,
`checked_shapes`, `status`, `violations`, and `report_path`. The built-in
engine uses KLayout Python to scan shape bounding boxes for simple min-width
violations. It is not a replacement for a process-specific DRC deck.

## `run_process_drc`

Inputs:

- `gds_path`
- `deck_path`
- `output_name`
- `klayout_executable`

Output uses schema `text-to-gds.drc.v0`, records the external command, writes a
normalized `.process.drc.json`, and parses `.lyrdb` or JSON reports when the
external KLayout command writes one. If the executable is not installed or the
deck command fails, the tool falls back to KLayout Python process rules when
the Python module is available. The report includes the external return code,
warnings, checked shape counts, and spacing-pair counts when produced by the
fallback.

## `run_simulation`

Inputs:

- `sidecar_path`
- `simulator`
- `jc_ua_per_um2`
- `shunt_capacitance_ff`
- `analysis_mode`: `auto`, `multiport_ljpa`, or `single_port_reflection`.
- `pump_current_fraction`
- `coupling_capacitance_ff`
- `resonator_capacitance_ff`
- `adapter_executable`
- `target_frequency_ghz`
- `target_gain_db`
- `target_bandwidth_mhz`
- `flux_bias_phi0`
- `squid_asymmetry`
- `flux_sweep_span_phi0`
- `flux_sweep_points`
- `flux_period_current_ma`
- `flux_mutual_inductance_ph`

Output uses schema `text-to-gds.simulation.v0` and includes junction area,
critical current, Josephson inductance, `physical_performance`, `result_path`,
`plot_path`, and `scientific_plot_path`. `physical_performance` carries
input/output ports and layout-derived metrics such as LJPA gain, bandwidth,
loaded Q, pump current, saturation/P1dB, noise temperature, or via-chain
resistance/topology. Every run writes both a quick `.simulation.png` and a
scientific PNG/SVG/CSV/JSON package. For
`simulator = "josim"`, `simulator = "ngspice"`, or
`simulator = "JosephsonCircuits.jl"`, the tool writes adapter artifacts and
executes the local command when the executable exists. The ngspice adapter
writes `.ngspice.cir`, `.ngspice.dat`, `.ngspice.log`, and `.ngspice.json`,
using a linearized JJ transient deck or LJPA two-port RLC starter depending on
the sidecar. The JosephsonCircuits adapter uses `analysis_mode="auto"` by
default. It writes a two-port LJPA harmonic-balance starter for
`lumped_element_jpa_seed` sidecars with `rf_in` and `rf_out` ports, returning
S11/S21/S12/S22 gain arrays plus peak/center S21 metrics and 3 dB bandwidth
when Julia executes it. Standalone JJ sidecars fall back to the single-port
reflection harmonic-balance starter.

For LJPA/SQUID sidecars, `physical_performance.flux_tuning` uses schema
`text-to-gds.squid-flux-modulation.v0` and records the low-loop-inductance
dc-SQUID Aharonov-Bohm modulation model, operating point, sweep table,
flux-tuned `Ic`, `Lj`, resonance frequency, optional coil current, and tuning
range.

Keep all tool returns JSON-serializable. Add fields only in a backward-compatible
way.

## `list_pcells`

Output uses schema `text-to-gds.pcells.v0` and includes registered PCell names
plus the active process stack.

## `extract_layout`

Inputs:

- `sidecar_path`
- `include_gds_shapes`

Output uses schema `text-to-gds.extraction-summary.v0` and includes
performance-relevant PCell parameters, layer stack metadata, ports, and optional
GDS layer bounding boxes.

## `run_magic_extract`

Inputs:

- `gds_path`
- `output_name`
- `top_cell`
- `tech_file`
- `magic_executable`

Output uses schema `text-to-gds.magic-extraction.v0` and includes generated
`.magic.tcl`, `.magic.json`, `.magic.spice`, and `.magic.ext` paths. If Magic
is unavailable, status is `skipped` and the TCL script/report still record the
attempt. Treat successful output as a layout-extraction handoff scaffold unless
a process-specific Magic tech file and calibrated stack were used.

## `list_simulators`

Output uses schema `text-to-gds.simulators.v0` and reports JosephsonCircuits.jl,
JoSIM, ngspice, PySpice, and Magic VLSI availability, executable names, source
URLs, and install hints. ngspice is executable through `run_simulation`; Magic
is executable through `run_magic_extract`; PySpice is a discovery/advisory entry
until an executable adapter is added.

## `list_research_integrations`

Output uses schema `text-to-gds.research-integrations.v0` and reports optional
upstream research adapters: gdsfactory, JosephsonCircuits.jl, scikit-rf,
openEMS, Optuna, Quantum Metal/Qiskit Metal, scqubits, and QCoDeS. Each entry
includes local availability, install hint, role, source URL, and expected
artifact families.

## `plan_ljpa`

Inputs:

- `prompt`

Output uses schema `text-to-gds.design-plan.v0` and includes target frequency,
bandwidth/gain assumptions, clarification questions, recommended PCells,
simulation adapters, and local workflow steps.

## `export_3d_preview`

Inputs:

- `gds_path`
- `output_name`

Output includes `html_path`, `json_path`, and `shape_count`. The preview is a
2.5D process-stack review aid, not an EM or field-solver result.

## `export_cad_artifacts`

Inputs:

- `gds_path`
- `output_name`

Output uses schema `text-to-gds.cad-export.v0` and includes a layer summary,
source GDS path, units, warnings, and derived file paths:

- `.layout.svg`
- `.layout.dxf`
- `.stack.stl`
- optional `.stack.glb`
- `.cad.json`

These are CAD-style inspection and interchange artifacts derived from GDS
bounding boxes. They are not a STEP source model, mask signoff, or EM result.

## `export_scientific_plot`

Inputs:

- `simulation_path`
- `output_name`
- `title`

Output uses schema `text-to-gds.scientific-plot.v0` and writes PNG, SVG, CSV,
and JSON metadata from a `.simulation.json`. Use it when a reviewer needs a
publication-style plot or raw numeric table instead of only the quick PNG.

## `export_rf_network`

Inputs:

- `simulation_path`
- `output_name`
- `reference_ohm`

Output uses schema `text-to-gds.rf-network.v0` and writes Touchstone `.s2p`,
`.rf.png`, `.rf.csv`, and `.rf.json` artifacts. If JosephsonCircuits supplied
S-parameter arrays, they are exported. Otherwise the tool writes a
layout-derived magnitude-only RF surrogate with zero phase and records that
validity limit.

## `export_openems_project`

Inputs:

- `sidecar_path`
- `output_name`
- `target_frequency_ghz`

Output uses schema `text-to-gds.openems-project.v0` and writes a generated
`.openems.py` script plus `.openems.json` metadata for CPW/resonator EM
handoff. The script is not executed by this MCP tool.

## `export_measurement_plan`

Inputs:

- `sidecar_path`
- `simulation_path`
- `output_name`

Output uses schema `text-to-gds.measurement-plan.v0` and writes a QCoDeS-style
`.qcodes.py` skeleton plus `.measurement.json` plan for VNA, pump, flux-bias,
and cryostat measurement handoff. It does not touch instruments.

## `export_hamiltonian_model`

Inputs:

- `sidecar_path`
- `output_name`
- `jc_ua_per_um2`
- `capacitance_ff`
- `flux_bias_phi0`
- `squid_asymmetry`

Output uses schema `text-to-gds.hamiltonian-model.v0` and writes a
scqubits-ready `.scqubits.py` script plus `.hamiltonian.json` with layout-derived
`EJ`, `EC`, estimated `f01`, and anharmonicity.

## `export_quantum_metal_bridge`

Inputs:

- `sidecar_path`
- `output_name`

Output uses schema `text-to-gds.quantum-metal-bridge.v0` and writes
`.qmetal.json` plus `.qmetal.py` mapping Text-to-GDS PCells, geometry, renderers,
and simulations onto Quantum Metal/Qiskit Metal concepts.

## `run_research_optimization`

Inputs:

- `sidecar_path`
- `output_name`
- `n_trials`
- `target_frequency_ghz`
- `target_gain_db`
- `target_bandwidth_mhz`
- `min_p1db_dbm`
- `force_fallback`

Output uses schema `text-to-gds.research-optimization.v0` and writes
`.optuna.json`, `.optuna.csv`, and `.optuna.png`. If Optuna is installed and
`force_fallback` is false, the tool uses an Optuna study. Otherwise it runs a
deterministic local grid over `Jc`, flux bias, SQUID asymmetry, pump fraction,
coupling capacitance, and bandwidth target.

## `run_traveling_wave_paper_benchmark`

Inputs:

- `output_name`

Output uses schema `text-to-gds.traveling-wave-paper-benchmark.v0` and writes
JSON, CSV, and PNG artifacts. It independently computes the Planat sample A/B
linear photonic gap and the first nine Erickson-Pappas KIT Floquet stop gaps.
The included 3WM/4WM gain curves use phase mismatch from the computed KIT bands,
but their peak coupling is calibrated to the paper. Read `parity_scope` before
using the result; the tool does not claim full nonlinear or noise parity.

## `run_gaydamachenko_jtwpa_benchmark`

Inputs:

- `output_name`
- `pump_frequency_ghz`

Output uses schema `text-to-gds.gaydamachenko-jtwpa-benchmark.v0` and writes
JSON, CSV, and PNG artifacts. The Appendix-B transfer matrices independently
compute finite-line `S11`/`S21`, Bloch stop bands, 3WM phase mismatch, and
coherence length. Nonlinear coupling and finite-line ripple amplitude are
declared paper calibrations because WRspice is not bundled.

## Closed-loop fabrication and measurement tools

- `list_fabrication_processes`: list process-run JSON records.
- `plan_process_aware_jpa`: parse a GHz target and named process, correct JJ
  area from measured Jc, and report expected Ic yield.
- `run_uncertainty_analysis`: write Monte Carlo JSON/CSV/PNG yield evidence.
- `run_analytical_verification`: write Kerr-JPA theory and quantum-noise
  comparison JSON/PNG, optionally including simulation and measurement JSON.
- `export_hfss_project`: write process-mapped HFSS driven/eigenmode build scripts.
- `export_pyaedt_project`: write or run the complete HFSS/Q3D automation bundle.
- `export_q3d_extract`: write or run Q3D capacitance-matrix extraction.
- `recommend_pyaedt_design_correction`: turn EM frequency/impedance error into
  first-order Optuna geometry seeds.
- `run_pyaedt_design_iteration`: regenerate supported LJPA/CPW GDS from one
  HFSS-derived frequency/impedance correction and run DRC.
- `run_pyaedt_benchmarks`: compare licensed solver JSON with registered targets;
  missing solver outputs remain explicit skips.
- `export_sonnet_project`: write SonnetLab build script and manifest.
- `export_epr_analysis`: write a pyEPR HFSS workflow and optionally compute
  participation/loss/T1 from field-energy JSON.
- `export_measurement_recipe`: write one of six QCoDeS-oriented recipe scripts.
- `analyze_cryostat_input_chain`: calculate attenuation, thermalization, noise,
  JPA-plane power, and compression headroom.
- `run_paper_benchmarks`: run all registered reproductions with explicit
  pass/fail/skip status.
- `record_experiment_feedback`: store design and measurement JSON in SQLite and
  return frequency/JJ-area correction factors.

## `run_parameter_sweep`

Inputs:

- `sidecar_path`
- `sweep_parameter`
- `start`
- `stop`
- `points`
- simulation defaults such as `jc_ua_per_um2`, target frequency/bandwidth,
  pump fraction, coupling capacitance, resonator capacitance, and shunt
  capacitance
- flux defaults such as `flux_bias_phi0`, `squid_asymmetry`,
  `flux_sweep_span_phi0`, `flux_sweep_points`, `flux_period_current_ma`, and
  `flux_mutual_inductance_ph`

Supported `sweep_parameter` values are `jc_ua_per_um2`, `junction_area_um2`,
`shunt_capacitance_ff`, `target_frequency_ghz`, `target_bandwidth_mhz`,
`pump_current_fraction`, `coupling_capacitance_ff`, and
`resonator_capacitance_ff`, `flux_bias_phi0`, and `squid_asymmetry`. Output uses schema
`text-to-gds.parameter-sweep.v0` and writes JSON plus PNG/SVG/CSV plot
artifacts.

## `run_validation_checklist`

Inputs:

- `gds_path`
- `sidecar_path`
- `drc_path`
- `extraction_path`
- `simulation_path`
- `cad_path`
- `output_name`

Output uses schema `text-to-gds.validation-roadmap.v0` and writes
`.validation.json`. It follows `Text-to-GDS_Academic_Industrial_Validation_Roadmap.md`
as an evidence checklist across layout, DRC, extraction, simulation, CAD, and
publication-readiness gates. It is bookkeeping, not foundry or publication
signoff by itself.

## `run_design_workflow`

Inputs:

- `prompt`
- `output_name`
- `parameters`
- `jc_ua_per_um2`
- `simulator`
- `analysis_mode`
- `pump_current_fraction`
- `coupling_capacitance_ff`
- `resonator_capacitance_ff`
- flux tuning parameters from `run_simulation`

Output uses schema `text-to-gds.design-workflow.v0` and includes plan,
compile, built-in DRC, process DRC adapter report, extraction, Magic extraction
handoff, 2.5D preview, simulation, validation, plot, and workbench sections. It writes a
`.workbench.html` local browser dashboard. The workflow also emits CAD export
artifacts, scientific simulation plot/data artifacts, and `.validation.json`.

## `run_optimized_design_workflow`

Inputs:

- `prompt`
- `output_name`
- `parameters`
- `jc_ua_per_um2`
- `max_iterations`
- `simulator`
- `analysis_mode`
- `pump_current_fraction`
- `coupling_capacitance_ff`
- `resonator_capacitance_ff`

Output is the same shape as `run_design_workflow`, with an additional
`optimization` section containing surrogate targets, final parameters, final
metrics, final errors, and iteration history.
