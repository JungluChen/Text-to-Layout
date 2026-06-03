# Benchmark 01: Manhattan Josephson Junction

## Prompt

Create a Manhattan Josephson Junction using the registered
`manhattan_josephson_junction` PCell. Use the default process layers, write a
GDS file, emit a semantic sidecar, run DRC with `min_width_um = 0.1`, and
estimate `Ic` and `Lj` for `Jc = 2.0 uA/um^2`.

## Expected Workflow

1. Instantiate the registered PCell instead of drawing raw polygons.
2. Write `workspace/artifacts/manhattan_jj.gds`.
3. Emit `workspace/artifacts/manhattan_jj.sidecar.json`.
4. Run the KLayout-backed built-in min-width DRC.
5. Run ideal JJ simulation from the sidecar.

## Expected Values

```text
junction_width_um = 0.22
junction_height_um = 0.22
junction_area_um2 = 0.0484
jc_ua_per_um2 = 2.0
critical_current_ua = 0.0968
josephson_inductance_ph = 3399.855149
```

## Expected Artifact Family

```text
Output layout: workspace/artifacts/manhattan_jj.gds
Layout screenshot: workspace/artifacts/manhattan_jj.layout.png
Semantic sidecar: workspace/artifacts/manhattan_jj.sidecar.json
DRC report: workspace/artifacts/manhattan_jj.drc.json
Simulation report: workspace/artifacts/manhattan_jj.sidecar.simulation.json
```
