# Text-to-GDS Workflow

## Compile

Use `compile_layout` for registered PCells. It writes:

- `.gds`: layout artifact.
- `.layout.png`: layout screenshot for quick visual inspection.
- `.sidecar.json`: schema, PCell name, GDS path, bounding box, ports, and PCell
  metadata.

Default artifact root is `workspace/artifacts/`.

## DRC

Use `run_drc` after every compile. The current built-in report uses KLayout
Python to read GDS and scan shape bounding boxes for simple min-width findings.
It preserves the schema `text-to-gds.drc.v0` so future process DRC decks can
replace the internal scan without changing agent loops.

## Simulation

Use `run_simulation` when a sidecar includes junction metadata. The built-in
ideal JJ adapter
computes:

- critical current from `junction_area_um2 * jc_ua_per_um2`
- Josephson inductance from `Phi0 / (2*pi*Ic)`

Future JosephsonCircuits.jl or JoSIM adapters should preserve the JSON result
shape and add engine-specific fields.

## Reporting

Return the generated paths, check status, key sidecar facts, and assumptions.
Avoid saying a foundry process was verified unless the process-specific DRC deck
actually ran.
