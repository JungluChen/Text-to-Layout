# Benchmark 06: Via-Chain Process Monitor

## Prompt

Area: Fit a 100-stage via-chain monitor inside $120 \mu m \times 30 \mu m$ on a
$5 mm \times 5 mm$ process-control die.

Layer Stack: Use M1/M2/M3 routing with alternating via stacks between adjacent
segments.

Performance Targets: Keep every via landing pad at least 0.4 um wide, target
total chain resistance under 50 ohms, and flag any open-chain topology in the
sidecar.

## Expected Workflow

1. Generate alternating M1/M2/M3 route segments and via-stack markers.
2. Emit a sidecar with `input` and `output` ports.
3. Run DRC and verify the generated 100-stage topology.
4. Record first-order resistance and open-chain checks in
   `physical_performance`.

## Expected Values

```text
stage_count = 100
checked_shapes = 504
input_port = input on layer [3, 0] at [-5.0, 0.0]
output_port = output on layer [3, 0] at [104.0, 0.0]
estimated_total_resistance_ohm = 27.7725
open_chain_detected = false
```

## Expected Artifact Family

```text
Output layout: workspace/artifacts/via_chain_monitor.gds
Layout screenshot: workspace/artifacts/via_chain_monitor.layout.png
Semantic sidecar: workspace/artifacts/via_chain_monitor.sidecar.json
DRC report: workspace/artifacts/via_chain_monitor.drc.json
Simulation/analysis report: workspace/artifacts/via_chain_monitor.simulation.json
```
