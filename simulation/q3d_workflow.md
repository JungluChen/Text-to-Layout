# Q3D Workflow (Capacitance / Inductance extraction)

> Manual workflow. Ansys Q3D Extractor computes quasi-static C/L/R matrices —
> the right tool for an IDC's capacitance.

## 1. Import the layout
- `POST /layout/export?format=gds` → import GDSII into Q3D.
- The two IDC combs become the two conductor nets (use ports `P1`, `P2`).

## 2. Assign conductors and nets
- Assign each comb (everything galvanically connected to `P1` vs `P2`) to a
  distinct **net**.
- Set conductor material (metal conductivity / thickness).

## 3. Dielectric environment
- Add the substrate dielectric below the metal and the air above; set
  permittivities. The interdigital capacitance is dominated by the substrate.

## 4. Solve
- Run the **Capacitance** solution (CG matrix).
- Read the mutual capacitance between the two nets — that is the IDC capacitance.

## 5. Compare to the target and loop
- Example target: 0.6 pF.
- If extracted C is low, increase `finger_pairs` or `overlap_um` in the Layout
  DSL; if high, decrease them. Regenerate (verification re-runs automatically),
  then re-extract.

## Sanity cross-check
- The generator's `estimated_capacitance_fF` (labelled low-confidence) gives an
  order-of-magnitude starting guess only. Q3D is the authority.
