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
- `adapter_executable`
- `target_frequency_ghz`
- `target_gain_db`
- `target_bandwidth_mhz`

Output uses schema `text-to-gds.simulation.v0` and includes junction area,
critical current, Josephson inductance, and `result_path`. For `simulator =
"josim"` or `simulator = "JosephsonCircuits.jl"`, the tool writes adapter
artifacts and executes the local command when the executable exists.

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

## `list_simulators`

Output uses schema `text-to-gds.simulators.v0` and reports JosephsonCircuits.jl
and JoSIM availability, executable names, source URLs, and install hints.

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

## `run_design_workflow`

Inputs:

- `prompt`
- `output_name`
- `parameters`
- `jc_ua_per_um2`
- `simulator`

Output uses schema `text-to-gds.design-workflow.v0` and includes plan,
compile, built-in DRC, process DRC adapter report, extraction, 2.5D preview,
simulation, and workbench sections. It writes a `.workbench.html` local browser
dashboard.

## `run_optimized_design_workflow`

Inputs:

- `prompt`
- `output_name`
- `parameters`
- `jc_ua_per_um2`
- `max_iterations`
- `simulator`

Output is the same shape as `run_design_workflow`, with an additional
`optimization` section containing surrogate targets, final parameters, final
metrics, final errors, and iteration history.
