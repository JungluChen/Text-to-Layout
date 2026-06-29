# ADS Workflow (Circuit / EM co-simulation)

> Manual workflow. Keysight ADS is best for circuit-level S-parameters,
> harmonic balance, and EM/circuit co-simulation.

## 1. Bring in the geometry
- Option A: import the GDS into the **ADS Layout** and run **Momentum** (2.5-D
  method-of-moments) for planar S-parameters.
- Option B: import an `.s2p` exported from HFSS and use it as a data item in a
  **schematic**.

## 2. Define the substrate
- In Momentum, create a substrate definition matching the fabrication stack
  (dielectric heights, permittivities, metal layers mapped from GDS layers).

## 3. Ports
- Place ports at `P1`/`P2`; assign the ground reference.

## 4. Simulate
- **Momentum** S-parameter sweep for the planar response, or
- **Harmonic Balance** when the device is embedded in a nonlinear circuit
  (e.g. a resonator coupled to an active element).

## 5. Extract and loop
- Pull S-parameters, insertion loss, resonance, and (for filters) bandwidth.
- Compare to target; adjust the **Layout DSL** and regenerate.

## When to prefer ADS over HFSS
- Planar, layered structures where 2.5-D MoM is sufficient and faster.
- Designs that need circuit-level co-simulation with packaged components.
- Use HFSS instead for fully 3-D structures, tight Q estimation, or strong
  out-of-plane coupling.
