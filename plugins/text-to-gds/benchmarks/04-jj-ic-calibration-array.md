# Benchmark 04: JJ Critical-Current Calibration Array

## Prompt

Area: Place 16 Josephson Junction test devices inside a
$60 \mu m \times 12 \mu m$ active array region on a $5 mm \times 5 mm$ die.

Layer Stack: Use M1 bottom electrode, M2 top electrode, and M3 probe routing.

Performance Targets: Sweep junction area from $0.04 \mu m^2$ to
$0.20 \mu m^2$, keep probe pads outside the active array, and report the
expected critical current for $J_c = 2.0 uA/\mu m^2$.

## Expected Workflow

1. Compile the registered `jj_ic_calibration_array` PCell with unique sidecar
   entries for each JJ.
2. Preserve area and layer metadata per junction.
3. Run DRC on all active shapes.
4. Report ideal critical current for each area point.

## Expected Artifact Family

```text
Output layout: workspace/artifacts/jj_ic_calibration_array.gds
Layout screenshot: workspace/artifacts/jj_ic_calibration_array.layout.png
Semantic sidecar: workspace/artifacts/jj_ic_calibration_array.sidecar.json
DRC report: workspace/artifacts/jj_ic_calibration_array.drc.json
Simulation/analysis report: workspace/artifacts/jj_ic_calibration_array.simulation.json
```
