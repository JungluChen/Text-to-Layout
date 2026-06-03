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

## `run_simulation`

Inputs:

- `sidecar_path`
- `simulator`
- `jc_ua_per_um2`
- `shunt_capacitance_ff`

Output uses schema `text-to-gds.simulation.v0` and includes junction area,
critical current, Josephson inductance, and `result_path`.

Keep all tool returns JSON-serializable. Add fields only in a backward-compatible
way.
