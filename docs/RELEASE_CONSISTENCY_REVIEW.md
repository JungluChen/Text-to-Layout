# Release consistency review

Review scope: public README, dependency metadata, CLI and doctor output,
showcase and legacy benchmark packets, solver discovery, simulation adapters,
claim validation, and committed evidence artifacts.

## Current public README contradictions

The previous public README mixed an old "FasterCap absent" demonstration with
committed FasterCap-backed showcase results. It also described the spiral as
FastHenry input-only and the test chip as geometry-only after local solver
capabilities had changed. The release README now reports current committed
results per artifact folder, keeps legacy analytical benchmarks separate, and
links each showcase row to its report, simulation record, and workflow trace.

## Executed real solvers

| Example | Executed solver | Scope | Result |
| --- | --- | --- | --- |
| 01 IDC | FasterCap 6.0.7 | IDC capacitance | 0.598641 pF versus 0.600000 pF; 0.226% error; `PHYSICS_VERIFIED` |
| 03 IDC + CPW | FasterCap 6.0.7 | Embedded IDC extraction region only | 0.610019 pF versus 0.600000 pF; 1.670% error; `PHYSICS_VERIFIED` for that region only |
| 04 spiral | FastHenry 3.0.1 | Spiral inductance | 2.958308 nH versus 3.000000 nH; 1.390% error; `PHYSICS_VERIFIED` |
| 06 test chip map | FasterCap and FastHenry 3.0.1 | Geometry-identical IDC and spiral sub-blocks | Sub-block evidence only; no full-tile solve |

Every executed record retains the command, return code, runtime, stdout,
stderr, solver-owned result, parser identity, extracted value, and target
comparison when a target exists.

## Analytical-only and solver-skipped examples

- Example 02 CPW remains `SKIPPED_SOLVER_ABSENT` for the executable workflow.
  openEMS and CSXCAD binaries are present, but the required Octave frontend is
  not available, so no S-parameter output exists.
- Example 05 quarter-wave resonator remains `SKIPPED_SOLVER_ABSENT`; its
  lambda/4 value is analytical and no EM resonance result exists.
- Example 06 remains `ANALYTICAL_ONLY` at full-tile scope. Its
  `tile_simulation_map.json` separates executed IDC/spiral sub-blocks from the
  prepared CPW route and unmodeled whole-tile interactions.

## Upgrade opportunities

- CPW and resonator can be upgraded when a compatible Octave plus openEMS
  frontend is installed and produces parseable Touchstone output.
- The spiral is `PHYSICS_VERIFIED` after two FastHenry-guided geometry
  iterations while retaining the 5% evidence gate.
- WRspice and PSCAN2 remain optional and missing. JoSIM is installed, but none
  of the six showcase prompts requests a qualified JJ circuit simulation.
- A real full-tile model requires ports, boundaries, mesh convergence,
  inter-block coupling, package assumptions, and a retained solver output.

## Fabrication status

All six examples remain `NOT_FABRICATION_READY`. The generic technology is not
a foundry PDK; process-specific DRC, finite-thickness and full-wave correlation,
package modeling, expert review, and measurement validation are still missing.
