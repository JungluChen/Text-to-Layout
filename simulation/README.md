# Open-Source Simulation Workflow

Simulation is evidence only when a real solver runs and produces a non-empty solver-owned artifact. Prepared input files are useful, but their status is `input_files_prepared`, not `executed`.

## Readiness levels

| Level | Requirement |
| - | - |
| 0 | Analytical estimate only |
| 1 | Geometry generated and verified |
| 2 | Open-source simulation input/script exists |
| 3 | Real simulation result generated |
| 4 | Result compared against the Layout DSL target |
| 5 | Optimization loop implemented |

## Base open-source paths

| Component/quantity | Tool | Repository workflow | Status |
| - | - | - | - |
| IDC capacitance matrix | FasterCap/FastCap | [`idc_fastercap/`](idc_fastercap/) | Level 2 |
| CPW Z0, S11, S21 | openEMS + scikit-rf | [`cpw_openems/`](cpw_openems/) | Blocked on explicit ground-reference ports |
| Spiral L, R, Q | FastHenry/FastHenry2 | [`spiral_fasthenry/`](spiral_fasthenry/) | Blocked on generator |
| Resonator f0, Q, S21 | openEMS + scikit-rf | [`resonator_openems/`](resonator_openems/) | Blocked on topology |
| General FDTD | Meep | Future connector | Planned |
| Electrostatic/FEM cross-check | Elmer FEM | Future connector | Planned |

FasterCap uses the FastCap2-compatible generic input format. The IDC adapter writes metre-scale `Q` panels and a list file, then records its zero-thickness/effective-medium assumptions. openEMS supports Python-driven FDTD and explicit port APIs; future CPW/resonator execution must retain the generated model, solver version, logs, and Touchstone output.

## IDC preparation

```bash
python simulation/idc_fastercap/generate_fastercap_input.py \
  examples/benchmarks/01_idc_0p6pf/layout.json \
  --out examples/benchmarks/01_idc_0p6pf/simulation
```

This produces `idc.qui`, `idc.lst`, and `simulation_manifest.json`. It does not produce a capacitance result.

```bash
python simulation/idc_fastercap/run_fastercap.py \
  examples/benchmarks/01_idc_0p6pf/layout.json
```

If no executable is installed, the runner exits with code 2 and reports `status=skipped`. It writes `simulation_result.json` only after a real solver returns a parseable capacitance matrix.

## Commercial correlation

The [Q3D](q3d_workflow.md), [HFSS](hfss_workflow.md), [ADS](ads_workflow.md), and [Sonnet](sonnet_workflow.md) guides remain available for higher-fidelity or independent correlation. They are not required for the base open-source preparation workflow and are never reported as executed without artifacts.
