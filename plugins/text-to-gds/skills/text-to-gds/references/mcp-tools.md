# MCP Tool Contract

## `compile_layout`

Inputs:

- `pcell`: registered PCell name.
- `parameters`: JSON object passed to the PCell.
- `output_name`: artifact filename.

Output includes `status`, `gds_path`, and `sidecar_path`.

## `run_drc`

Inputs:

- `gds_path`
- `ruleset`
- `min_width_um`

Output uses schema `text-to-gds.drc.v0` and includes `status`,
`violations`, and `report_path`.

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

