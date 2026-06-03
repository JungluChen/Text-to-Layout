# Text-to-GDS Workflow

## Compile

Use `compile_layout` for registered PCells. It writes:

- `.gds`: layout artifact.
- `.sidecar.json`: schema, PCell name, GDS path, bounding box, ports, and PCell
  metadata.

Default artifact root is `workspace/artifacts/`.

## DRC

Use `run_drc` after every compile. Phase 1 returns a mock report shaped as
`text-to-gds.drc.v0`; future KLayout integration should preserve this schema so
agent loops do not change.

## Simulation

Use `run_simulation` when a sidecar includes junction metadata. The Phase 1 mock
computes:

- critical current from `junction_area_um2 * jc_ua_per_um2`
- Josephson inductance from `Phi0 / (2*pi*Ic)`

Future JosephsonCircuits.jl or JoSIM adapters should preserve the JSON result
shape and add engine-specific fields.

## Reporting

Return the generated paths, check status, key sidecar facts, and assumptions.
Avoid saying a foundry process was verified unless the process-specific DRC deck
actually ran.

