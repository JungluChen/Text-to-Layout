# HFSS Workflow (S-parameters, resonance, Q)

> Manual workflow. Ansys HFSS is a commercial full-wave 3-D FEM solver; this
> document describes the hand-off, not an automated driver.

## 1. Import the layout
- Generate GDS: `POST /layout/export?format=gds` (or `textlayout generate`).
- In HFSS, **Modeler → Import → GDSII**. Map GDS layer numbers to 3-D sheets:
  - `M1` (1/0) → signal/ground metal sheet (perfect E or finite conductivity).
  - `GND` (10/0) → ground plane.

## 2. Build the stack-up
- Add the substrate (e.g. high-resistivity Si or sapphire) as a 3-D box below the metal.
- Set metal thickness (or use 2-D sheets with surface impedance for thin films /
  superconductors).

## 3. Assign materials and boundaries
- Metal: `pec` for an ideal first pass, or a finite-conductivity / impedance
  boundary for loss (essential for Q).
- Substrate: set permittivity and loss tangent.
- Radiation/airbox or symmetry boundaries as appropriate.

## 4. Define ports
- Use the ports declared on the generated component (`P1`, `P2` for IDC/CPW) as
  lumped or wave-port locations.
- Reference each port to the adjacent ground.

## 5. Solve and extract
- **Driven Modal/Terminal** solution; sweep the frequency band of interest.
- Extract: S-parameters (`.s2p`), resonance frequency (S21 peak/notch),
  loaded/unloaded Q (from the resonance bandwidth).

## 6. Feed back
- Compare extracted values to the design target.
- Adjust the **Layout DSL** parameters and regenerate — never hand-edit the GDS.
