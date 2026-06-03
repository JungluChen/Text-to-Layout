# Benchmark 02: Compact CMOS Logic Cell

## Prompt

Area: The active circuit must occupy no more than $5 \mu m \times 5 \mu m$
within a larger $5 mm \times 5 mm$ die.

Layer Stack: Assume a 3-metal layer process (M1 for local interconnects, M2/M3
for routing).

Performance Targets: Optimize for a propagation delay under 50 ps and a leakage
power under 100 nW at 1.8 V.

## Expected Workflow

1. Convert the prompt into explicit layout, layer, and verification targets.
2. Use registered PCells or adapter-provided standard cells where available.
3. Write GDS and semantic sidecar artifacts.
4. Run DRC.
5. Emit a simulation report that records unsupported delay/leakage targets as
   pending adapter requirements if no SPICE/timing adapter is installed.

## Expected Artifact Family

```text
Output layout: workspace/artifacts/compact_cmos_logic.gds
Layout screenshot: workspace/artifacts/compact_cmos_logic.layout.png
Semantic sidecar: workspace/artifacts/compact_cmos_logic.sidecar.json
DRC report: workspace/artifacts/compact_cmos_logic.drc.json
Simulation/analysis report: workspace/artifacts/compact_cmos_logic.simulation.json
```
