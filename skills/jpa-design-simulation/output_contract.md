# Output Contract

Use this canonical directory for a JPA run:

```text
out/jpa_demo/
|-- intent.json
|-- design_equations.json
|-- layout.json
|-- output.gds
|-- output.svg
|-- verification.json
|-- extraction/
|   |-- capacitance_input/
|   `-- capacitance_result.json
|-- simulation/
|   |-- josim/
|   |-- pscan2/
|   |-- wrspice/
|   `-- simulation.json
|-- optimization.json
`-- report.md
```

## File requirements

- `intent.json`: schema version, source prompt, normalized requirements, units, assumptions, constraints, backend policy, and tolerances.
- `design_equations.json`: constants, equations, substitutions, results, units, sources, practical bounds, and limitations.
- `layout.json`: typed Layout DSL, technology/layer map reference, generator names/versions, deterministic parameters, and stable identifiers.
- `output.gds`: deterministic layout generated from `layout.json`; record its hash.
- `output.svg`: deterministic human preview from the same layout source. It is visualization, not verification evidence.
- `verification.json`: checks, measured values, limits, pass/fail, GDS readback, source hashes, and tool versions.
- `extraction/capacitance_input/`: geometry/material/net files, manifest, command template, units, and source-layout hash.
- `extraction/capacitance_result.json`: backend/status, command/version, native output paths, parsed capacitance, units, conductor mapping, target/tolerance, and diagnostics. Write an honest skipped or failed record when no value was extracted.
- `simulation/{josim,pscan2,wrspice}/`: backend deck/project, manifest, command, logs, raw outputs, and parsed result when applicable.
- `simulation/simulation.json`: per-backend prepared/executed/parsed/checked states, metrics, tolerances, artifact paths, and evidence labels.
- `optimization.json`: ordered iterations, input/output artifact hashes, parameter changes, objectives, evidence invalidation, convergence, and stop reason.
- `report.md`: target/result comparison, assumptions, topology, equations, layout checks, extraction and simulation evidence, exact labels, failures, limitations, and reproduction commands.

## Integrity rules

- Use atomic writes for structured records when implementation begins.
- Store paths relative to `out/jpa_demo/` when practical and include content hashes for dependency tracking.
- Never create fabricated native outputs to satisfy this tree.
- When an upstream stage fails, omit impossible downstream geometry/native files and explain the incomplete packet in structured status records and `report.md`.
- A preview image or GDS existence alone does not establish correct connectivity, capacitance, resonance, gain, or fabrication readiness.
