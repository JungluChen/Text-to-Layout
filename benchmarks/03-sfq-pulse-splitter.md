# Benchmark 03: SFQ Pulse Splitter

## Prompt

Area: Fit the active splitter cell within $20 \mu m \times 20 \mu m$ and place
it inside a $5 mm \times 5 mm$ superconducting test die.

Layer Stack: Use a niobium 3-metal stack with M1 for ground/local return, M2
for Josephson Junction wiring, and M3 for crossovers.

Performance Targets: Target output skew below 2 ps, junction critical current
of 100 uA per branch, and no routing segment narrower than 0.25 um.

## Expected Workflow

1. Instantiate reviewed JJ and superconducting-routing PCells.
2. Emit ports for bias, input, and both outputs in the semantic sidecar.
3. Run DRC with a 0.25 um min-width threshold.
4. Compute ideal JJ values and record skew as requiring JoSIM or
   JosephsonCircuits.jl.

## Expected Artifact Family

```text
Output layout: workspace/artifacts/sfq_pulse_splitter.gds
Semantic sidecar: workspace/artifacts/sfq_pulse_splitter.sidecar.json
DRC report: workspace/artifacts/sfq_pulse_splitter.drc.json
Simulation/analysis report: workspace/artifacts/sfq_pulse_splitter.simulation.json
```
