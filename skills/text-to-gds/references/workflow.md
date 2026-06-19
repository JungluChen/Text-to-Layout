# Text-to-GDS Workflow

## Compile

Use `compile_layout` for registered PCells. It writes:

- `.gds`: layout artifact.
- `.layout.png`: layout screenshot for quick visual inspection.
- `.sidecar.json`: schema, PCell name, GDS path, bounding box, ports, and PCell
  metadata.

Default artifact root is `workspace/artifacts/`.

Use `list_pcells` when choosing available PCells. Current starter cells include
JJ, CPW, meander inductor, flux-bias line, via stack, via-chain monitor, and
ground plane cells.

## DRC

Use `run_drc` after every compile. The current built-in report uses KLayout
Python to read GDS and scan shape bounding boxes for simple min-width findings.
It preserves the schema `text-to-gds.drc.v0` so future process DRC decks can
replace the internal scan without changing agent loops.

Use `run_process_drc` when a process deck should be attempted. It invokes
external `klayout -b -rd input=... -rd report=... -r deck.drc` when the binary
is installed. If the binary is missing or cannot execute the deck, it falls
back to KLayout Python process rules derived from `DEFAULT_PROCESS` and records
the external command/warnings in the report. Treat this fallback as a local
iteration gate, not foundry signoff.

Use `run_magic_extract` when a Magic VLSI extraction handoff should be
attempted. It writes a `.magic.tcl` script, imports GDS, runs Magic extraction,
and attempts `ext2spice` export when Magic is installed. If Magic is missing,
the status is `skipped` and the generated script still shows the intended local
handoff. Treat output as calibrated extraction only when a process-specific
Magic tech file is supplied and validated.

## Simulation

Run `extract_layout` before simulator handoff. It makes layer/material,
thickness, width, length, gap, angle, area, ports, and GDS shape boxes explicit
for the next tool.

Use `run_simulation` when a sidecar includes junction metadata. The built-in
ideal JJ adapter
computes:

- critical current from `junction_area_um2 * jc_ua_per_um2`
- Josephson inductance from `Phi0 / (2*pi*Ic)`

For `lumped_element_jpa_seed`, the sidecar marks an explicit two-junction
`dc_squid_pair`. `run_simulation` applies the low-loop-inductance SQUID
Aharonov-Bohm modulation when flux parameters are supplied:

- `flux_bias_phi0`
- `squid_asymmetry`
- `flux_period_current_ma` or `flux_mutual_inductance_ph`

The report includes `physical_performance.flux_tuning` with operating-point
`Ic(Phi)`, `Lj(Phi)`, `f0(Phi)`, coil current, and a flux sweep.

Every simulation also includes `physical_performance`. Report this section when
the user asks for physical parameters. LJPA sidecars include input/output ports,
estimated gain, 3 dB bandwidth, loaded Q, pump current, resonator/coupling
capacitance, quantum noise temperature, and estimated saturation/P1dB. Via-chain
sidecars include stage count, input/output ports, estimated resistance, and
open-chain topology status.

Use `list_simulators` to check whether Julia/JosephsonCircuits.jl, JoSIM, or
ngspice are available. `run_simulation(..., simulator="josim")` writes and runs
a JoSIM transient starter deck when `josim-cli` is available. It records stdout,
stderr, return code, the `.josim.csv` path, and parsed transient rows.
`run_simulation(..., simulator="ngspice")` writes and runs a generated ngspice
starter deck when `ngspice` is available. Standalone JJ sidecars use a
linearized `Lj` transient deck; LJPA sidecars use a small-signal two-port RLC
deck. It records stdout, stderr, return code, `.ngspice.dat`, `.ngspice.log`,
`.ngspice.json`, parsed rows, and the simulation plot.
`run_simulation(..., simulator="JosephsonCircuits.jl")` writes and runs a Julia
harmonic-balance starter model when Julia is available. With
`analysis_mode="auto"`, LJPA sidecars generated from `lumped_element_jpa_seed`
select the two-port S-parameter model and record S11/S21/S12/S22 gain arrays,
peak S21 gain, center S21 gain, target errors, and 3 dB bandwidth. Standalone
JJ sidecars fall back to the single-port reflection model. Do not claim any
external simulator ran unless the result status is `executed`, and do not treat
the starter model as EM, extracted SPICE, or foundry signoff.
Every simulation writes a `.simulation.png` plot beside the JSON report. It
also writes `.scientific.png`, `.scientific.svg`, `.scientific.csv`, and
`.scientific.json` for review documents and numerical handoff. Use the quick
PNG as the first visual evidence for circuit iteration, and use the scientific
package when a user asks for publication-quality plots or data tables.

Use `run_parameter_sweep` for local sensitivity studies across `Jc`, junction
area, target frequency, target bandwidth, pump current, coupling capacitance,
resonator capacitance, shunt capacitance, flux bias, or SQUID asymmetry. It
writes JSON plus PNG/SVG/CSV trend artifacts. Treat sweeps as first-order
layout-derived studies unless an external simulator replaces the rows.

Use `export_rf_network` after simulation when the user asks for S-parameters,
Touchstone, scikit-rf, VNA-style review, or RF plots. It writes `.s2p`,
`.rf.png`, `.rf.csv`, and `.rf.json`. Unless the upstream adapter supplied
complex S-parameters, this is a magnitude-only export with zero phase.

Use `list_research_integrations` before choosing optional research adapters.
Use `export_openems_project` for EM solver handoff, `export_measurement_plan`
for QCoDeS/lab handoff, `export_hamiltonian_model` for scqubits handoff,
`export_quantum_metal_bridge` for Quantum Metal/Qiskit Metal architecture
mapping, and `run_research_optimization` for Optuna-style constrained search.
State clearly whether an external package actually ran or whether only a
handoff scaffold was generated.

## Planning

Use `plan_ljpa` for open-ended prompts such as "Design a 5 GHz LJPA with wide
bandwidth". Ask the returned material, process, gain, bandwidth, noise, pump,
and simulator questions before locking the design.

Use `run_design_workflow` for a first-pass local artifact set. It compiles the
`lumped_element_jpa_seed` PCell, runs built-in DRC, attempts process DRC, runs
extraction, attempts Magic extraction, writes an interactive stack preview,
runs simulation, exports CAD artifacts, writes quick/scientific plots, writes
RF/Touchstone artifacts, writes the validation roadmap checklist, and writes a
`.workbench.html` dashboard.
Pass `simulator="josim"`, `simulator="ngspice"`, or
`simulator="JosephsonCircuits.jl"` when the
prompt-to-layout run should include an external adapter result in the same
workflow response.

Use `run_optimized_design_workflow` when the request asks to optimize or
iterate. The current optimizer is a local surrogate loop over CPW length/gap
and JJ dimensions; it must be replaced by external simulator metrics for
signoff-grade optimization.

Use `python skills/text-to-gds/scripts/text_to_gds_tool.py ui` to serve the
live local workbench. The page accepts prompt edits, simulator selection,
analysis mode, pump fraction, coupling capacitance, resonator capacitance, and
can run normal or optimized workflows from the browser.

## 3D/Stack Preview

Use `export_3d_preview` after compile to write `.stack3d.html` and
`.stack3d.json`. This is a local 2.5D review aid based on layer bounding boxes,
not an EM model. The HTML includes browser-side rotate controls for quick
layout-stack inspection.

## CAD/Interchange Export

Use `export_cad_artifacts` after compile when the user asks for CAD-style
review, vector interchange, or a 3D stack solid. It writes `.layout.svg`,
`.layout.dxf`, `.stack.stl`, optional `.stack.glb`, and `.cad.json` from GDS
layer bounding boxes. GDS remains the source of truth; these derived files are
for inspection and handoff, not mask signoff or mechanical STEP source.

## Validation Roadmap

Use `run_validation_checklist` to write `.validation.json` from the generated
GDS, sidecar, DRC, extraction, simulation, and CAD reports. It follows the
academic/industrial roadmap checklist and marks missing evidence as warnings.
Do not treat a passing checklist as publication or foundry signoff unless the
underlying external DRC, EM extraction, harmonic-balance, and measurement
evidence actually exists.

## Reporting

Return the generated paths, check status, key sidecar facts, and assumptions.
Avoid saying a foundry process was verified unless the process-specific DRC deck
actually ran.
