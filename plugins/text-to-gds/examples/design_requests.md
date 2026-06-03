# Design Request Examples

These examples show the kind of structured prompt an agent should turn into a
Text-to-GDS layout workflow. Each request should produce a GDS artifact, a
semantic sidecar, a DRC report, and a simulation or analysis report when the
required adapter exists.

## 1. Compact CMOS Logic Cell

```text
Area: The active circuit must occupy no more than $5 \mu m \times 5 \mu m$
within a larger $5 mm \times 5 mm$ die.
Layer Stack: Assume a 3-metal layer process (M1 for local interconnects,
M2/M3 for routing).
Performance Targets: Optimize for a propagation delay under 50 ps and a
leakage power under 100 nW at 1.8 V.
```

Expected outputs:

```text
Output layout: workspace/artifacts/compact_cmos_logic.gds
Layout screenshot: workspace/artifacts/compact_cmos_logic.layout.png
Semantic sidecar: workspace/artifacts/compact_cmos_logic.sidecar.json
DRC report: workspace/artifacts/compact_cmos_logic.drc.json
Simulation/analysis report: workspace/artifacts/compact_cmos_logic.simulation.json
```

Adapter note: layout generation and DRC are Text-to-GDS responsibilities.
Propagation delay and leakage require a SPICE or Liberty/timing adapter; the
current JJ simulator must not be used to claim CMOS delay or leakage.

## 2. SFQ Pulse Splitter

```text
Area: Fit the active splitter cell within $20 \mu m \times 20 \mu m$ and place
it inside a $5 mm \times 5 mm$ superconducting test die.
Layer Stack: Use a niobium 3-metal stack with M1 for ground/local return,
M2 for Josephson Junction wiring, and M3 for crossovers.
Performance Targets: Target output skew below 2 ps, junction critical current
of 100 uA per branch, and no routing segment narrower than 0.25 um.
```

Expected outputs:

```text
Output layout: workspace/artifacts/sfq_pulse_splitter.gds
Layout screenshot: workspace/artifacts/sfq_pulse_splitter.layout.png
Semantic sidecar: workspace/artifacts/sfq_pulse_splitter.sidecar.json
DRC report: workspace/artifacts/sfq_pulse_splitter.drc.json
Simulation/analysis report: workspace/artifacts/sfq_pulse_splitter.simulation.json
```

Adapter note: the current ideal JJ calculation can report junction-derived
values, but skew requires a JosephsonCircuits.jl, JoSIM, or WRSPICE adapter.

## 3. JJ Critical-Current Calibration Array

```text
Area: Place 16 Josephson Junction test devices inside a
$60 \mu m \times 12 \mu m$ active array region on a $5 mm \times 5 mm$ die.
Layer Stack: Use M1 bottom electrode, M2 top electrode, and M3 probe routing.
Performance Targets: Sweep junction area from $0.04 \mu m^2$ to
$0.20 \mu m^2$, keep probe pads outside the active array, and report the
expected critical current for $J_c = 2.0 uA/\mu m^2$.
```

Expected outputs:

```text
Output layout: workspace/artifacts/jj_ic_calibration_array.gds
Layout screenshot: workspace/artifacts/jj_ic_calibration_array.layout.png
Semantic sidecar: workspace/artifacts/jj_ic_calibration_array.sidecar.json
DRC report: workspace/artifacts/jj_ic_calibration_array.drc.json
Simulation/analysis report: workspace/artifacts/jj_ic_calibration_array.simulation.json
```

Adapter note: this is directly aligned with the current ideal JJ calculation
when each junction area is represented in the sidecar.

## 4. CPW Resonator Test Structure

```text
Area: Route one quarter-wave CPW resonator in a $2 mm \times 2 mm$ region inside
a $5 mm \times 5 mm$ die.
Layer Stack: Use M1 as a continuous ground plane, M2 as the resonator trace,
and M3 for airbridge or crossover markers.
Performance Targets: Target a 6.0 GHz fundamental mode, coupling quality
factor above $1 \times 10^5$, and minimum CPW gap of 6 um.
```

Expected outputs:

```text
Output layout: workspace/artifacts/cpw_resonator_test.gds
Layout screenshot: workspace/artifacts/cpw_resonator_test.layout.png
Semantic sidecar: workspace/artifacts/cpw_resonator_test.sidecar.json
DRC report: workspace/artifacts/cpw_resonator_test.drc.json
Simulation/analysis report: workspace/artifacts/cpw_resonator_test.simulation.json
```

Adapter note: geometry and DRC are local Text-to-GDS outputs. Resonant
frequency and quality factor require a microwave or EM extraction adapter.

## 5. Via-Chain Process Monitor

```text
Area: Fit a 100-stage via-chain monitor inside $120 \mu m \times 30 \mu m$ on a
$5 mm \times 5 mm$ process-control die.
Layer Stack: Use M1/M2/M3 routing with alternating via stacks between adjacent
segments.
Performance Targets: Keep every via landing pad at least 0.4 um wide, target
total chain resistance under 50 ohms, and flag any open-chain topology in the
sidecar.
```

Expected outputs:

```text
Output layout: workspace/artifacts/via_chain_monitor.gds
Layout screenshot: workspace/artifacts/via_chain_monitor.layout.png
Semantic sidecar: workspace/artifacts/via_chain_monitor.sidecar.json
DRC report: workspace/artifacts/via_chain_monitor.drc.json
Simulation/analysis report: workspace/artifacts/via_chain_monitor.simulation.json
```

Adapter note: min-width and geometry checks are in scope for the current DRC
scan. Resistance extraction and open-chain topology require an extraction
adapter.
