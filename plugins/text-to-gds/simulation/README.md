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
| CPW Z0, S11, S21 | openEMS + scikit-rf | [`cpw_openems/`](cpw_openems/) | Level 2 |
| Spiral L, R, Q | FastHenry/FastHenry2 | [`spiral_fasthenry/`](spiral_fasthenry/) | Level 2 |
| Resonator f0, Q, S21 | openEMS + scikit-rf | [`resonator_openems/`](resonator_openems/) | Level 2 |
| SQUID loop/JJ response | FastHenry + Josephson circuit solver | benchmark manifest | Level 1; foundry stack missing |
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

## CPW, spiral, and resonator preparation

```bash
python simulation/cpw_openems/generate_openems_model.py examples/benchmarks/02_cpw_50ohm/layout.json --out examples/benchmarks/02_cpw_50ohm/simulation
python simulation/spiral_fasthenry/generate_fasthenry_input.py examples/benchmarks/03_spiral_inductor/layout.json --out examples/benchmarks/03_spiral_inductor/simulation
python simulation/resonator_openems/generate_openems_model.py examples/benchmarks/04_quarter_wave_resonator/layout.json --out examples/benchmarks/04_quarter_wave_resonator/simulation
```

These commands verify geometry and prepare solver inputs. They do not execute openEMS or FastHenry.

## Commercial correlation

The [Q3D](q3d_workflow.md), [HFSS](hfss_workflow.md), [ADS](ads_workflow.md), and [Sonnet](sonnet_workflow.md) guides remain available for higher-fidelity or independent correlation. They are not required for the base open-source preparation workflow and are never reported as executed without artifacts.
