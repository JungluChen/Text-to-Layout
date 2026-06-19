# Research Integrations

Text-to-GDS does not vendor upstream source code. It distills the useful
architecture and file contracts into local adapter surfaces that can call the
upstream tools when they are installed.

## Integration Map

| Project | Crucial part merged into Text-to-GDS |
| --- | --- |
| gdsfactory | PCell-first layout generation, explicit ports, GDS output, and process metadata. |
| JosephsonCircuits.jl | Generated Julia harmonic-balance starter scripts for single-port JJ reflection and two-port LJPA S-parameters. |
| scikit-rf | Touchstone `.s2p` RF-network export path and optional inspection backend. |
| openEMS | Generated CPW/resonator EM handoff script for future `Z0`, field map, and S-parameter extraction. |
| Optuna | Optional study/trial optimizer backend with deterministic fallback. |
| Quantum Metal / Qiskit Metal | Component -> geometry -> renderer -> analysis architecture bridge metadata. |
| scqubits | Layout-derived `EJ`, `EC`, `f01`, and anharmonicity handoff script. |
| QCoDeS | VNA, pump, flux-bias, and cryostat measurement-plan template. |
| JTWPA transfer-matrix engine | Typed periodic-cell configurations, vectorized finite-line S-parameters, Bloch dispersion, stop-band detection, phase mismatch, coherence length, and reduced 3WM gain. |
| pyEPR | Generated `ProjectInfo`/`DistributedAnalysis`/`QuantumAnalysis` workflow plus field-energy participation, loss, and T1 calculation. |
| Ansys HFSS/Q3D / PyAEDT | Process-mapped GDS import, driven/eigenmode solves, fields, S-parameters, capacitance matrices, and optimization feedback. |
| Sonnet Suites / SonnetLab | Generated planar GDS import and frequency-sweep script. |

## New MCP Tools

- `list_research_integrations`
- `export_rf_network`
- `export_openems_project`
- `export_measurement_plan`
- `export_hamiltonian_model`
- `export_quantum_metal_bridge`
- `run_research_optimization`
- `run_gaydamachenko_jtwpa_benchmark`
- `export_epr_analysis`
- `export_hfss_project`
- `export_pyaedt_project`
- `export_q3d_extract`
- `recommend_pyaedt_design_correction`
- `run_pyaedt_design_iteration`
- `run_pyaedt_benchmarks`
- `export_sonnet_project`
- `export_measurement_recipe`
- `run_uncertainty_analysis`
- `run_analytical_verification`
- `run_paper_benchmarks`

## Artifact Contracts

`export_rf_network` writes:

- `.s2p`
- `.rf.png`
- `.rf.csv`
- `.rf.json`

`export_openems_project` writes:

- `.openems.py`
- `.openems.json`

Expected future openEMS runtime files:

- `s_parameters.s2p`
- `characteristic_impedance.json`
- `E_field.vtk`
- `current_density.vtk`

`export_measurement_plan` writes:

- `.measurement.json`
- `.qcodes.py`

`export_hamiltonian_model` writes:

- `.hamiltonian.json`
- `.scqubits.py`

`export_quantum_metal_bridge` writes:

- `.qmetal.json`
- `.qmetal.py`

`run_research_optimization` writes:

- `.optuna.json`
- `.optuna.csv`
- `.optuna.png`

`run_gaydamachenko_jtwpa_benchmark` writes:

- `.json` with paper checks, typed configuration, stop bands, gain, and scaling metadata
- `.csv` with signal/idler frequencies, phase mismatch, and gain
- `.png` with gain, reflection/stop bands, and phase mismatch

`export_pyaedt_project` writes a license-free automation bundle:

- `.config.json` with GDS layer elevations, thicknesses, substrate, ports, and review gates
- `.hfss.py` for driven-modal and eigenmode designs
- `.q3d.py` for capacitance extraction
- `.aedt`, `.s2p`, `.eigenmode.json`, `.q3d.matrix.csv`, and field PNGs after licensed execution

## Validity

These adapters are designed for local iteration and reproducible handoff. They
do not replace process-specific DRC, extracted parasitics, EM mesh validation,
calibrated pump models, measured VNA data, or cryogenic experiment signoff.
