# Test-chip tile evidence dashboard

> This is a layout integration candidate with sub-block evidence, not a full-chip EM-verified design. Inter-block coupling, package, transitions, and whole-tile modes are not modeled.

## Full tile

- Full-tile solver executed: **False**
- Full-tile status: **NOT_MODELED**
- Full-tile verified: **False**
- Full-tile solver: `Gmsh + Palace`
- Reason: Palace full-tile inputs prepared; solver not executed because Palace is missing.

## Sub-blocks

| Sub-block | Solver | Status | Extracted | Target | Error | Within tolerance |
| --- | --- | --- | --- | --- | --- | --- |
| IDC | FasterCap | SIMULATION_EXECUTED | 0.6973109999999999 | 0.6 | 16.218% | False |
| CPW | openEMS+scikit-rf | SIMULATION_EXECUTED | 38.47287247108259 | 50.0 | -23.054% | False |
| SpiralInductor | fasthenry | SIMULATION_EXECUTED | - | - | - | FastHenry extraction of the geometry-identical spiral sub-block; no tile prompt target |
| Resonator | openEMS+scikit-rf | SIMULATION_EXECUTED | 3.0 | 6.0 | -50.0% | False |
| AlignmentMarksAndLabels | none | GEOMETRY_ONLY | - | - | - | Non-electrical geometry; no solver model applies. |

This is a research layout integration candidate with sub-block evidence, not a full-chip EM-verified design.

