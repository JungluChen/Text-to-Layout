# Text-to-GDS Workflow

## Compile

Use `compile_layout` for registered PCells. It writes:

- `.gds`: layout artifact.
- `.layout.png`: layout screenshot for quick visual inspection.
- `.sidecar.json`: schema, PCell name, GDS path, bounding box, ports, and PCell
  metadata.

Default artifact root is `workspace/artifacts/`.

Use `list_pcells` when choosing available PCells. Current starter cells include
JJ, CPW, meander inductor, flux-bias line, via stack, and ground plane cells.

## DRC

Use `run_drc` after every compile. The current built-in report uses KLayout
Python to read GDS and scan shape bounding boxes for simple min-width findings.
It preserves the schema `text-to-gds.drc.v0` so future process DRC decks can
replace the internal scan without changing agent loops.

## Simulation

Run `extract_layout` before simulator handoff. It makes layer/material,
thickness, width, length, gap, angle, area, ports, and GDS shape boxes explicit
for the next tool.

Use `run_simulation` when a sidecar includes junction metadata. The built-in
ideal JJ adapter
computes:

- critical current from `junction_area_um2 * jc_ua_per_um2`
- Josephson inductance from `Phi0 / (2*pi*Ic)`

Use `list_simulators` to check whether Julia/JosephsonCircuits.jl or JoSIM are
available. `run_simulation(..., simulator="josim")` writes a starter JoSIM deck.
`run_simulation(..., simulator="JosephsonCircuits.jl")` writes an adapter
command plan. Do not claim either external simulator ran until the adapter
actually executes the local tool.

## Planning

Use `plan_ljpa` for open-ended prompts such as "Design a 5 GHz LJPA with wide
bandwidth". Ask the returned material, process, gain, bandwidth, noise, pump,
and simulator questions before locking the design.

## 3D/Stack Preview

Use `export_3d_preview` after compile to write `.stack3d.html` and
`.stack3d.json`. This is a local 2.5D review aid based on layer bounding boxes,
not an EM model.

## Reporting

Return the generated paths, check status, key sidecar facts, and assumptions.
Avoid saying a foundry process was verified unless the process-specific DRC deck
actually ran.
