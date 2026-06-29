# Sonnet Workflow (Planar EM)

> Manual workflow. Sonnet is appropriate for planar metal patterns in a layered dielectric stack. This guide does not claim a solver run.

## Setup

1. Import `output.gds` and map the GDS layer/datatype to a Sonnet metal level.
2. Define the substrate thickness, relative permittivity, loss tangent, metal thickness or sheet impedance, and air/cover layers.
3. Set the analysis box far enough from the IDC and refine the cell size around finger gaps and tips.
4. Place ports on the two IDC buses at `P1` and `P2`; confirm the reference conductor and de-embedding plane.
5. Sweep from well below the operating frequency through the expected self-resonance.

## Extract and compare

- Export Touchstone data from Sonnet.
- Derive low-frequency capacitance from the two-port admittance and locate the first self-resonance.
- Record convergence versus cell size and box size.
- Compare the extracted capacitance with `target.capacitance_pf` and the analytical estimate.
- Change only Layout DSL parameters, regenerate, and rerun verification before the next solve.

Treat the result as executed evidence only when the Sonnet project, version, log, and non-empty Touchstone output are retained.
