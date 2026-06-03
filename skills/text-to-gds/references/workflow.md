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

Use `run_process_drc` when a process deck should be attempted. It invokes
external `klayout -b -rd input=... -rd report=... -r deck.drc` when the binary
is installed. If KLayout is unavailable, the result is `skipped`, not `passed`.

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
script. When the executable is installed or passed through `adapter_executable`,
the adapter runs the local command and records stdout, stderr, return code, and
parsed output. Do not claim either external simulator ran unless the result
status is `executed`.

## Planning

Use `plan_ljpa` for open-ended prompts such as "Design a 5 GHz LJPA with wide
bandwidth". Ask the returned material, process, gain, bandwidth, noise, pump,
and simulator questions before locking the design.

Use `run_design_workflow` for a first-pass local artifact set. It compiles the
`lumped_element_jpa_seed` PCell, runs built-in DRC, attempts process DRC, runs
extraction, writes a stack preview, runs the deterministic JJ simulation, and
writes a `.workbench.html` dashboard.

Use `run_optimized_design_workflow` when the request asks to optimize or
iterate. The current optimizer is a local surrogate loop over CPW length/gap
and JJ dimensions; it must be replaced by external simulator metrics for
signoff-grade optimization.

Use `python skills/text-to-gds/scripts/text_to_gds_tool.py ui` to serve the
live local workbench. The page accepts prompt edits and can run normal or
optimized workflows from the browser.

## 3D/Stack Preview

Use `export_3d_preview` after compile to write `.stack3d.html` and
`.stack3d.json`. This is a local 2.5D review aid based on layer bounding boxes,
not an EM model.

## Reporting

Return the generated paths, check status, key sidecar facts, and assumptions.
Avoid saying a foundry process was verified unless the process-specific DRC deck
actually ran.
