# Benchmark 05: CPW Resonator Test Structure

## Prompt

Area: Route one quarter-wave CPW resonator in a $2 mm \times 2 mm$ region inside
a $5 mm \times 5 mm$ die.

Layer Stack: Use M1 as a continuous ground plane, M2 as the resonator trace,
and M3 for airbridge or crossover markers.

Performance Targets: Target a 6.0 GHz fundamental mode, coupling quality factor
above $1 \times 10^5$, and minimum CPW gap of 6 um.

## Expected Workflow

1. Compile the registered `cpw_quarter_wave_resonator` PCell with trace,
   boolean ground clearance, feedline, and short-via geometry.
2. Store resonator length, trace width, gap, and coupling region in the sidecar.
3. Run DRC for min-width and min-gap constraints where supported.
4. Record the synthesized length from
   $l=c/(4f\sqrt{\varepsilon_{eff}})$ and mark quality factor as requiring
   microwave or EM extraction if no adapter is installed.

## Expected Artifact Family

```text
Output layout: workspace/artifacts/cpw_resonator_test.gds
Layout screenshot: workspace/artifacts/cpw_resonator_test.layout.png
Semantic sidecar: workspace/artifacts/cpw_resonator_test.sidecar.json
DRC report: workspace/artifacts/cpw_resonator_test.drc.json
Simulation/analysis report: workspace/artifacts/cpw_resonator_test.simulation.json
```
