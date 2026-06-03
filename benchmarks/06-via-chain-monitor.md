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
2. Emit a sidecar with ordered chain nodes and expected connectivity.
3. Run DRC with a 0.4 um landing-pad threshold.
4. Record resistance and open-chain checks as requiring extraction if no
   connectivity adapter is installed.

## Expected Artifact Family

```text
Output layout: workspace/artifacts/via_chain_monitor.gds
Semantic sidecar: workspace/artifacts/via_chain_monitor.sidecar.json
DRC report: workspace/artifacts/via_chain_monitor.drc.json
Simulation/analysis report: workspace/artifacts/via_chain_monitor.simulation.json
```
