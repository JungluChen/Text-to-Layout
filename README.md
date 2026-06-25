<div align="center">

# Text-to-GDS

**Solver-first superconducting quantum layout automation.**

*Physics-grounded orchestration from natural-language prompt to GDSII, extraction, solver inputs, review, and explicit signoff status.*

[Benchmarks](#-benchmarks) ??[Real results](#-real-solver-results) ??[How it works](#%EF%B8%8F-how-it-works) ??[Installation](#-installation)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](pyproject.toml)
[![Backends](https://img.shields.io/badge/Backends-6%20live%20%7C%203%20pending-00A676?style=flat-square)](#backend-status)
[![MCP](https://img.shields.io/badge/MCP-94%20tools-6B46C1?style=flat-square)](src/text_to_gds/server.py)

</div>

---

> **The promise is not "here is a layout proven to work."**
> It is **"here is the evidence for each stage, and where evidence is missing."**

Text-to-GDS runs a physics compiler: every derived number must trace to geometry, an explicit process input, a real solver output file, or imported measurement data. `source = "LLM"` is an invalid provenance label. A skipped solver is reported as `SKIPPED` and never counts as signoff evidence.

Key contracts:

- [SOLVER_EVIDENCE_CONTRACT.md](SOLVER_EVIDENCE_CONTRACT.md)
- [PHYSICS_GRAPH_SCHEMA.md](PHYSICS_GRAPH_SCHEMA.md)
- [SIGNOFF_CRITERIA.md](SIGNOFF_CRITERIA.md)

---

## What makes this different

| Capability | Text-to-GDS | Typical AI layout tool |
|---|---|---|
| Rejects its own layout if physics fails | **Yes** | No |
| Every signoff number requires `value + unit + source + method + confidence + file_path` | **Yes** | No |
| JosephsonCircuits.jl harmonic-balance handoff and execution audit | **Yes** | No |
| scqubits Hamiltonian handoff and execution audit | **Yes** | No |
| EM solver input generation plus output-file validation | **Yes** | No |
| 5-agent review committee (physics / microwave / fab / measurement / literature) | **Yes** | No |
| Auto-repair loop reports accepted or failed status | **Yes** | No |
| Reports `SKIPPED`, never `PASSED`, when solver is unavailable | **Yes** | No |
| Solver agreement engine requires independent evidence | **Yes** | No |
| External backend bootstrap and status checker | **Yes** | No |

---

## Backend Evidence Status

The sections below separate executed solver results from installed, binary-found,
input-prepared, skipped, and planned backends. A solver only counts as executed
when a solver-owned output file exists.

### JosephsonCircuits.jl ??JPA harmonic balance (`executed`)

```
Device:      Lumped-element JPA seed, 6 GHz target
Solver:      JosephsonCircuits.jl v0.5.2 (harmonic balance)
Runtime:     Julia 1.12.6 @ .tools/julia-1.12.6/

Extracted:   Ic = 0.658 ??   (from junction area Jc = 2.0 ??/????
             Lj = 500.0 pH   (???/2?Ic)
             Cr = 1.255 pF   (resonator capacitance)
             Cc = 0.125 pF   (coupling capacitance)

Pump:        f_pump = 6.0 GHz
```

<img src="assets/jpa_analysis_example.png" alt="JPA gain from JosephsonCircuits.jl harmonic balance" width="680">

### scqubits ??Transmon energy spectrum (`executed`)

```
Device:      Layout-derived TunableTransmon from LJPA JJ geometry
Solver:      scqubits 4.3.1 (exact diagonalisation, ncut=51)
Runtime:     Python 3.11 in-process

Extracted:   A = 0.387 ????  (junction area from GDS)
             Ic = 0.548 ??   (Jc = 2.0 ??/????
             Lj = 601.0 pH
             C  = 1170.7 fF

Computed:    Ej/h = 272.0 GHz
             Ec/h =  16.5 MHz
             Ej/Ec = 16 445       (deep transmon regime)

Energy levels (flux = 0.25 ???):
             |0????|1??  f????= 5.029 GHz
             |1????|2??  f?頩? = 5.012 GHz
             Anharmonicity ??= ??6.7 MHz
```

<img src="assets/scqubits_spectrum_example.png" alt="Transmon energy spectrum from scqubits" width="680">

### openEMS FDTD ??RF S-parameters (`binary found, ready to run`)

```
Executable:  .tools/openEMS-v0.0.36/openEMS/openEMS.exe
Status:      SKIPPED in this documentation run (full CPW mesh not configured)
Activate:    export_openems_project(sidecar_path, run=True)
Output:      Touchstone .s2p + characteristic impedance Z0
```

<img src="assets/openems_extraction_example.png" alt="openEMS extraction status panel" width="680">

---

## ???Full pipeline figures

Every figure below is produced by the physics-first pipeline.  Solver panels
show **EXECUTED** (green), **SKIPPED** (grey), or **FAILED** (red) status
for each solver stage.  A skipped solver means the binary was unavailable
during the documentation run — it is not a failure, but it is not evidence.

<table>
  <tr>
    <td align="center"><b>Manhattan JJ ??3-panel benchmark</b><br>
    GDS geometry ??extraction.json ??solver evidence<br>
    <img src="assets/benchmark_01_manhattan_jj_layout.png" width="340"></td>
    <td align="center"><b>CPW quarter-wave resonator ??3-panel</b><br>
    6 GHz ??50 ????openEMS-ready<br>
    <img src="assets/benchmark_05_cpw_resonator_test_layout.png" width="340"></td>
  </tr>
  <tr>
    <td align="center"><b>JJ calibration array ??extraction sweep</b><br>
    Ic sweep from junction area metadata<br>
    <img src="assets/benchmark_04_jj_ic_calibration_array_layout.png" width="340"></td>
    <td align="center"><b>SFQ pulse splitter ??JoSIM-ready</b><br>
    josim-cli at .tools/josim-v2.7/<br>
    <img src="assets/benchmark_03_sfq_pulse_splitter_layout.png" width="340"></td>
  </tr>
  <tr>
    <td align="center"><b>Process stack extraction</b><br>
    Layer-resolved geometry ??EM model<br>
    <img src="assets/hfss_stack_3d.png" width="340"></td>
    <td align="center"><b>10-panel scientific lineage report</b><br>
    Every value with provenance chain<br>
    <img src="assets/scientific_report_example.png" width="340"></td>
  </tr>
</table>

---

## ??Quick start

**1. Describe your device**

```text
Design a 6 GHz JPA with 20 dB gain and 200 MHz bandwidth.
Jc = 2.0 ??/???? junction width = 0.22 ??.
Include flux line, pump port, and wirebond pads.
```

**2. Compile through the physics gate**

```python
from text_to_gds.design_intent import synthesize_design_intent
from text_to_gds.server import compile_layout

intent = synthesize_design_intent(prompt, inputs=physics_targets)
# Raises immediately if targets are physically inconsistent.
# No layout is generated from an incoherent design intent.

result = compile_layout(pcell="lumped_element_jpa_seed", parameters=params)
# result["gds_path"]      ??verified GDSII
# result["sidecar_path"]  ??semantic manifest (ports, layers, junctions)
```

**3. Extract with full provenance**

```python
from text_to_gds.server import extract_layout, extract_physics_graph_artifact

ext = extract_layout(result["sidecar_path"], jc_ua_per_um2=2.0)
graph = extract_physics_graph_artifact(
    result["sidecar_path"],
    jc_ua_per_um2=2.0,
    specific_capacitance_ff_per_um2=45.0,
)
# ext["result_path"]      -> extraction.json summary
# graph["result_path"]    -> physics_graph.json compiler IR
# graph["nodes"]          -> conductor, capacitor, inductor, JJ, CPW, port, ground
# graph["edges"]          -> electrical, capacitive, mutual, microwave-port relations
```

**4. Run real solvers**

```python
from text_to_gds.server import (
    export_openems_project,
    generate_josephsoncircuits_model_from_physics_graph,
    generate_solver_inputs_from_physics_graph,
    run_simulation,
)

solver_inputs = generate_solver_inputs_from_physics_graph(graph["result_path"])
model = generate_josephsoncircuits_model_from_physics_graph(graph["result_path"])

# JosephsonCircuits.jl harmonic balance ??real gain vs pump power
sim = run_simulation(result["sidecar_path"], simulator="JosephsonCircuits.jl",
                     jc_ua_per_um2=2.0, coupling_capacitance_ff=5.0)
# sim["adapter_status"] == "executed"  ??real solver ran
# sim["adapter_status"] == "skipped"   ??Julia not found, never faked

# scqubits ??real energy spectrum
spec = run_simulation(result["sidecar_path"], simulator="scqubits")
# spec["execution"]["f01_ghz"]           ??real eigenvalue
# spec["execution"]["anharmonicity_ghz"] ??real ??
# openEMS FDTD ??real S-parameters
em = export_openems_project(result["sidecar_path"], run=True)
# Returns status="executed" + .s2p Touchstone, or status="skipped" ??never faked
```

**5. Run the review committee**

```python
from text_to_gds.review.committee import run_review_committee

verdict = run_review_committee(result["gds_path"], result["sidecar_path"],
                               extraction=ext, simulation=sim)
# verdict["final_score"]  ??min(physics, microwave, fab, measurement, literature)
# verdict["blocking"]     ??list of hard failures
# verdict["pass"]         ??True only if final_score >= 90
# Auto-repair loop runs until accepted or budget exhausted.
```

**Full pipeline**

```
prompt
??design_intent.json      (physics feasibility gate ??blocks incoherent targets)
??LayoutBackend           (KQCircuits ??Qiskit Metal ??gdsfactory ??local_pcells)
??GDSII + sidecar.json
??DRC (KLayout)           (min width, spacing, layer mapping, JJ overlap)
??extraction.json         (every value: extracted | estimated | simulated | measured)
??physics_graph.json      (compiler IR; GDS is no longer the source of truth)
??EM solver               (openEMS / Palace / Elmer / FastCap)
??circuit solver          (JosephsonCircuits.jl / scqubits / JoSIM / ngspice)
??solver_agreement        (?? independent sources, confidence score)
??review_committee        (5 agents, score = min across all)
??auto-repair loop        (iterate until score ??90 or budget exhausted)
??signoff report          (PASS / FAIL, proven values table, next actions)
```

---

## 0-to-100 demo ladder

Current fabrication-real workflow demos:

```bash
uv run python examples/zero_to_one_demos.py all
uv run python examples/demo_A_physics_gate.py
uv run python examples/demo_B_full_extraction.py
uv run python examples/demo_C_simulation_solvers.py
uv run python examples/demo_D_review_and_signoff.py
uv run python examples/demo_E_full_pipeline_100.py
```

| Level | Demo file | New workflow coverage |
|---:|---|---|
| 0 | [`zero_to_one_demos.py 0`](examples/zero_to_one_demos.py) | Lists PCells, process kits, and EM solvers before layout. |
| 20 | [`zero_to_one_demos.py 20`](examples/zero_to_one_demos.py) | Manhattan JJ GDS, DRC, boolean overlap `JJ/M1/M2`, `extraction.json`, and `physics_graph.json`. |
| 40 | [`zero_to_one_demos.py 40`](examples/zero_to_one_demos.py) | CPW quarter-wave resonator, subtractive ground clearances, physical length, coupling capacitor, and EM solver input files. |
| 50 | [`demo_B_full_extraction.py`](examples/demo_B_full_extraction.py) | Full GDS-to-extraction chain with polygon-derived parameters and solver-input generation. |
| 75 | [`demo_C_simulation_solvers.py`](examples/demo_C_simulation_solvers.py) | scqubits/JosephsonCircuits handoffs and solver-status auditing; no gain plot unless nonlinear pump simulation executes. |
| 90 | [`demo_D_review_and_signoff.py`](examples/demo_D_review_and_signoff.py) | Review committee, signoff level 0-6, measurement plan, and blockers. |
| 100 | [`demo_E_full_pipeline_100.py`](examples/demo_E_full_pipeline_100.py) | End-to-end layout, DRC, extraction, physics graph, EM/circuit solver handoffs, review, signoff, report, and measurement recipe. |

For every demo above, screenshots are secondary. Acceptance comes from GDS polygons,
boolean extraction, provenance records, solver status, and validation output.

Each level proves a distinct contract. Run one file per level, or all at once:

```bash
uv run python examples/zero_to_one_demos.py all   # classic 6-level demos
uv run python examples/demo_A_physics_gate.py     # 0??5: physics gate
uv run python examples/demo_B_full_extraction.py  # 25??0: extraction pipeline
uv run python examples/demo_C_simulation_solvers.py # 50??5: real solvers
uv run python examples/demo_D_review_and_signoff.py # 75??0: 5-agent committee
uv run python examples/demo_E_full_pipeline_100.py  # 90??00: full 13-step run
```

| Level | Demo file | Key functions exercised | Proves |
|---:|---|---|---|
| 0 | `zero_to_one_demos.py 0` | `list_pcells`, `list_em_solvers`, `list_process_design_kits` | Capability index: PCells, PDKs, EM solvers. |
| 20 | `zero_to_one_demos.py 20` | `compile_layout`, `run_drc`, `extract_layout`, `extract_physics_graph_artifact` | JJ GDS ??DRC ??`extraction.json` ??`physics_graph.json`. |
| 25 | **`demo_A_physics_gate.py`** | `check_design_feasibility`, `synthesize_design_intent`, `compile_layout` | Physics gate blocks incoherent targets; only valid intent reaches GDS. |
| 40 | `zero_to_one_demos.py 40` | `extract_physics_graph_artifact`, `generate_solver_inputs_from_physics_graph`, `export_openems_project` | CPW graph ??openEMS `geometry.xml` + `mesh.xml` + `ports.xml`, Elmer and Palace inputs. |
| 50 | **`demo_B_full_extraction.py`** | `compile_layout`, `run_drc`, `extract_layout`, `extract_physics_graph_artifact`, `generate_solver_inputs_from_physics_graph` | Full extraction chain with provenance lineage on every value. |
| 60 | `zero_to_one_demos.py 60` | `run_inverse_design_jpa` | Every JPA optimizer candidate regenerates GDS before scoring. |
| 75 | **`demo_C_simulation_solvers.py`** | `run_simulation`, `export_hamiltonian_model`, `generate_josephsoncircuits_model_from_physics_graph`, `run_analytical_verification`, `cross_validate_solvers` | scqubits Hamiltonian + JosephsonCircuits.jl harmonic balance + analytical cross-check. |
| 80 | `zero_to_one_demos.py 80` | `compare_measurement_engine` | VNA-style CSV fit and process correction output. |
| 90 | **`demo_D_review_and_signoff.py`** | `review_layout`, `evaluate_signoff_level`, `validate_device_template`, `export_measurement_plan` | 5-agent committee, score = min across reviewers, signoff level 0??. |
| 100 | `zero_to_one_demos.py 100` | `run_axion_search_jpa_final_test` | GDS + physics graph + extracted LC + EM inputs + JosephsonCircuits handoff + gain map. |
| 100 | **`demo_E_full_pipeline_100.py`** | 13 functions end-to-end | Complete pipeline: intent ??layout ??DRC ??extract ??physics_graph ??EM/circuit solvers ??review ??signoff ??scientific report. |

---

## Truthfulness Contract

- `executed` means a real solver ran and produced an output file.
- `installed` means the dependency is importable or the binary exists; it did
  not necessarily run.
- `binary_found` means an executable was detected; it is not solver evidence.
- `input_files_prepared` means handoff files exist; it is not solver evidence.
- `skipped` means the solver was unavailable or intentionally not run.
- `planned` means future integration only.

Signoff labels are constrained:

- Level 5 or higher is required for `physics signoff`.
- Level 6 is required for `measurement-calibrated`.
- Skipped solvers, analytical estimates, and generated plots do not count as
  solver execution.

---

## ???Benchmarks

The `*_layout.png` assets are geometry-only layout thumbnails. Solver/status benchmark panels are generated separately as `*_benchmark.png` so layout assets are not overwritten by report graphics.

| # | Device | Prompt | Result |
|---|---|---|---|
| 1 | [Manhattan JJ](benchmarks/01-manhattan-josephson-junction.md) | Create a Manhattan JJ. Run DRC. Estimate `Ic` and `Lj` for `Jc = 2.0 ??/???迎葆. | <img src="assets/benchmark_01_manhattan_jj_layout.png" width="220"> |
| 2 | [Ground Plane Coupon](benchmarks/02-compact-cmos-logic-cell.md) | Isolated ground-plane process coupon, `5 ?? ? 5 ??`, 1 ?? clearance. | <img src="assets/benchmark_02_compact_cmos_logic_layout.png" width="220"> |
| 3 | [SFQ Pulse Splitter](benchmarks/03-sfq-pulse-splitter.md) | JJ splitter, `Ic = 0.3 ?? ? 0.3 ??`, 1 ?? leads. Branch Ic and min-width targets. | <img src="assets/benchmark_03_sfq_pulse_splitter_layout.png" width="220"> |
| 4 | [JJ Calibration Array](benchmarks/04-jj-ic-calibration-array.md) | Sweep JJ areas. Report expected critical current from sidecar metadata. | <img src="assets/benchmark_04_jj_ic_calibration_array_layout.png" width="220"> |
| 5 | [CPW Resonator](benchmarks/05-cpw-resonator-test.md) | CPW quarter-wave resonator, 6 GHz, 10 MHz bandwidth, 50 ?? | <img src="assets/benchmark_05_cpw_resonator_test_layout.png" width="220"> |
| 6 | [Via-Chain Monitor](benchmarks/06-via-chain-monitor.md) | 100-stage via-chain process monitor with resistance and topology targets. | <img src="assets/benchmark_06_via_chain_monitor_layout.png" width="220"> |

---

## ???Backend status

Text-to-GDS is an orchestration layer over real open-source quantum EDA tools. Every backend is cloned, importable, or binary-discovered ??not a toy simulator.

> Full install guide: [`EXTERNAL_BACKEND_INTEGRATION_STATUS.md`](EXTERNAL_BACKEND_INTEGRATION_STATUS.md)

### Layout backends

| Priority | Backend | Version | Status | Role |
|---|---|---|---|---|
| 1 | [**KQCircuits**](https://github.com/iqm-finland/KQCircuits) | 4.9.11 | **installed** | CPW layouts, resonators, airbridges, junction-compatible |
| 2 | [**gdsfactory**](https://github.com/gdsfactory/gdsfactory) | 9.43.0 | **installed** | Boolean ops, layer handling, export/import |
| 3 | [**Qiskit Metal**](https://github.com/Qiskit/qiskit-metal) | unknown | skipped (Win/Py3.12) | Transmon layout, CPW routing, launch pads |

### Simulation backends

| Backend | Version | Status | Role |
|---|---|---|---|
| [**JosephsonCircuits.jl**](https://github.com/kpobrien/JosephsonCircuits.jl) | 0.5.2 | executed where output file exists | JPA/JTWPA gain, pump sweep, harmonic balance |
| [**scqubits**](https://github.com/scqubits/scqubits) | 4.3.1 | executed where output file exists | Transmon/fluxonium spectra, anharmonicity |
| [**openEMS**](https://github.com/thliebig/openEMS) | 0.0.36 | binary found / input files prepared | RF S-parameters, CPW Z0, Touchstone .s2p |
| [**JoSIM**](https://github.com/JoeyDelp/JoSIM) | 2.7 | binary found | SFQ circuit timing simulation |
| [**pyEPR**](https://github.com/zlatko-minev/pyEPR) | 0.9.6 | installed | Energy participation ratios |
| [**Palace**](https://github.com/awslabs/palace) | unknown | skipped | Eigenmode f0, Q factor (requires CMake + MPI build) |
| [**Elmer FEM**](https://github.com/ElmerCSC/elmerfem) | unknown | skipped | Electrostatic capacitance (requires installer) |
| [**FastCap2**](https://github.com/ediloren/FastCap2) | unknown | planned / skipped until installed | Capacitance extraction |
| [**FastHenry2**](https://github.com/ediloren/FastHenry2) | unknown | planned / skipped until installed | Inductance extraction |

**`executed`** = real solver ran and produced output numbers used in this README.
**`binary found`** = executable at `.tools/` ??activate with one API call.
**`skipped`** = adapter returned `status="skipped"` ??explicit reason, no fake data.

---

## ???Skills

| Skill | Role | Source |
|---|---|---|
| **Text-to-GDS** | Core layout generation with PCells, DRC, and JJ simulation | [skills/text-to-gds](skills/text-to-gds/SKILL.md) |
| **Simulation** | JosephsonCircuits.jl, JoSIM, ngspice, scqubits handoffs | [skills/text-to-gds-simulation](skills/text-to-gds-simulation/SKILL.md) |
| **Circuit Design** | Pre-layout circuit target planning (JPA / CPW / qubit) | [skills/text-to-gds-circuit-design](skills/text-to-gds-circuit-design/SKILL.md) |
| **Layout Design** | Compile ??route ??DRC ??extract ??review | [skills/text-to-gds-layout-design](skills/text-to-gds-layout-design/SKILL.md) |
| **Signoff** | Artifact audit, DRC status, simulation check, release validation | [skills/text-to-gds-signoff](skills/text-to-gds-signoff/SKILL.md) |
| **Physics Signoff** | Full signoff engineer: rejects any layout that lacks solver evidence | [skills/text-to-gds-physics-signoff](skills/text-to-gds-physics-signoff/SKILL.md) |

---

## ???Installation

**Skills CLI:**

```bash
npx skills install JungluChen/Text-to-Layout
```

**Verified local development path** (Python 3.11+):

```bash
git clone https://github.com/JungluChen/Text-to-Layout.git
cd Text-to-Layout
uv sync
uv run pytest
uv run python examples/zero_to_one_demos.py all
```

Installed workflow commands:

```bash
uv run text-to-gds
uv run text-to-gds-simulation --check
uv run text-to-gds-circuit-design --check
uv run text-to-gds-layout-design --check
uv run text-to-gds-signoff --check
uv run text-to-gds-physics-signoff --check
```

**Check and set up external solver toolchains:**

```powershell
# See what's available on this machine
uv run python scripts/check_external_tools.py

# Clone optional external backend repos into .tools/repos
uv run python scripts/bootstrap_external_repos.py --clone

# Install missing Python packages and JosephsonCircuits.jl
uv run python scripts/setup_external_tools.py
```

Julia 1.12.6, JoSIM 2.7, and openEMS 0.0.36 are auto-discovered from `.tools/` ??no PATH configuration needed. See [`EXTERNAL_BACKEND_INTEGRATION_STATUS.md`](EXTERNAL_BACKEND_INTEGRATION_STATUS.md) for Palace and Elmer.

---

## ?? Examples

### Pipeline demos ??0 to 100 (newest workflow)

| Demo file | Level | Functions covered | What it proves |
|---|---:|---|---|
| [`demo_A_physics_gate.py`](examples/demo_A_physics_gate.py) | 0??5 | `check_design_feasibility`, `synthesize_design_intent`, `compile_layout` | Physics gate blocks incoherent targets before GDS is written. |
| [`demo_B_full_extraction.py`](examples/demo_B_full_extraction.py) | 25??0 | `compile_layout`, `run_drc`, `extract_layout`, `extract_physics_graph_artifact`, `generate_solver_inputs_from_physics_graph` | Full extraction with provenance lineage on Z0, 庰_eff, L', C', and solver input files. |
| [`demo_C_simulation_solvers.py`](examples/demo_C_simulation_solvers.py) | 50??5 | `run_simulation` (scqubits + JosephsonCircuits.jl), `export_hamiltonian_model`, `generate_josephsoncircuits_model_from_physics_graph`, `run_analytical_verification`, `cross_validate_solvers` | Real solver handoffs: scqubits Hamiltonian + JC.jl harmonic balance + analytical cross-check. |
| [`demo_D_review_and_signoff.py`](examples/demo_D_review_and_signoff.py) | 75??0 | `review_layout`, `evaluate_signoff_level`, `validate_device_template`, `export_measurement_plan` | 5-agent review committee (score = min), signoff level 0?? evaluation, measurement plan for level 6. |
| [`demo_E_full_pipeline_100.py`](examples/demo_E_full_pipeline_100.py) | 90??00 | 13 functions end-to-end | Complete run: intent ??GDS ??DRC ??extraction ??physics_graph ??EM/circuit solvers ??review ??signoff ??scientific report ??measurement recipe. |

### Classic demos

| Example | Backend | What it proves |
|---|---|---|
| [`zero_to_one_demos.py`](examples/zero_to_one_demos.py) | full compiler | Six runnable demos from 0 to 100: capabilities, JJ, CPW, inverse design, measurement feedback, axion JPA |
| [`examples/01_full_pipeline_jj.py`](examples/01_full_pipeline_jj.py) | JosephsonCircuits.jl | Full pipeline: intent ??GDS ??extract ??harmonic balance ??committee |
| [`examples/02_kqcircuits_cpw_resonator.py`](examples/02_kqcircuits_cpw_resonator.py) | KQCircuits + openEMS | CPW resonator ??FDTD ??Touchstone .s2p |
| [`examples/03_scqubits_transmon_spectrum.py`](examples/03_scqubits_transmon_spectrum.py) | scqubits | Extracted Ej/Ec ??exact diagonalisation ??f01, 帢 |
| [`examples/04_jpa_gain_josephsoncircuits.py`](examples/04_jpa_gain_josephsoncircuits.py) | JosephsonCircuits.jl | LJPA ??real gain curve ??only valid JPA gain source |
| [`examples/05_backend_status_and_provenance.py`](examples/05_backend_status_and_provenance.py) | all | 9-backend status table + value_record() provenance contract |

---

## ?雓? How it works

### Layout backends ??priority order

| Priority | Backend | When used |
|---|---|---|
| 1 | **KQCircuits** | Superconducting PCells with full process stack |
| 2 | **Qiskit Metal** | Transmon / qubit resonator geometries |
| 3 | **gdsfactory** | General parametric cells, routing, boolean ops |
| 4 | **local_pcells** | Tests and demos only ??never for production/tapeout |

`compile_supercad` returns `status="unsupported"` if no backend can handle the request. No fake layout is generated.

### Simulation backends

| Analysis | Open backend | Role |
|---|---|---|
| RF S-parameters / Z0 | **openEMS** (FDTD) | CPW characteristic impedance, S11/S21 |
| Eigenmode f0 / Q | **Palace** (3D FEM) | Cavity resonator modes |
| Capacitance / inductance | **Elmer / FastCap / FastHenry** | IDC coupling, qubit C matrix |
| Nonlinear JPA / JTWPA gain | **JosephsonCircuits.jl** | Pump sweep, gain vs frequency |
| Qubit Hamiltonian / spectrum | **scqubits** | f???? anharmonicity, energy levels |
| SFQ circuit timing | **JoSIM / ngspice** | Josephson voltage pulse propagation |
| Energy participation ratios | **pyEPR** | EPR from eigenmode field solution |

### Provenance labels

Every lineage entry in an extraction result carries a `method_label`:

| Label | Meaning |
|---|---|
| `extracted` | Measured from GDS geometry (e.g. junction overlap area) |
| `estimated` | Analytical formula (e.g. `Lj = ???/(2?Ic)`) ??sanity check only |
| `simulated` | Produced by a real solver output file |
| `measured` | Imported from experiment data |

No value may appear in a report without a lineage entry. `source = "LLM"` is invalid and causes immediate failure.

### Solver agreement engine

A single solver is never trusted. The agreement engine cross-checks a quantity across ??2 independent sources (analytical + FDTD + FEM) and returns a confidence score. Disagreement above tolerance blocks signoff.

### Five-agent review committee

Score = **minimum** across all five agents ??one critical failure cannot be averaged away.

| Agent | Checks |
|---|---|
| **Physics** | Topology, JJ connectivity, CPW ground-gap, impedance vs extracted L and C |
| **Microwave** | Port existence, S-parameter reciprocity/passivity, `.s2p` file present |
| **Fabrication** | DRC min-width/spacing, layer map, JJ overlap, via enclosure |
| **Measurement** | RF port, DC bias, flux line, pump port, wirebond/probe pads |
| **Literature** | Parameter plausibility vs known device classes |

Pass threshold: `final_score ??90`. Auto-repair loop iterates generate ??review ??fix until accepted or budget is spent.

### Hard stops

Immediately fails ??no repair loop:

- Solver panel says `SOLVER NOT EXECUTED` and report claims simulation
- Layout generated by local fallback when a professional backend is available
- CPW has no valid ground-gap-signal-ground structure
- JPA has no valid nonlinear pump model
- Report hides skipped solvers
- Any claimed value has no provenance

---

### Validity boundaries

This tool produces a **fabrication-real research prototype**, not a tapeout-ready design.

| What Text-to-GDS provides | What it does NOT provide |
|---|---|
| Boolean-subtracted ground planes, multi-layer JJ geometry | Foundry-calibrated PDK with measured Jc, film thickness |
| Conformal-mapping CPW impedance (analytical cross-check) | EM-converged S-parameters from FDTD/FEM (requires solver execution) |
| Provenance on every derived value | Measurement-calibrated process corners |
| DRC for minimum width/spacing/enclosure | Full foundry DRC deck (antenna, density, metal fill) |
| Junction area from boolean M1∩M2 overlap | Measured Ic from cryogenic probe station |
| Deterministic review committee with hard failure | Human expert review for tapeout signoff |

**To move from research prototype to tapeout:**
1. Replace generic process parameters with foundry-measured film data
2. Run EM solver to convergence (openEMS/Palace/HFSS) and verify against analytical
3. Fabricate test structures and measure Jc, via resistance, CPW loss
4. Feed measurement data back via `record_experiment_feedback()`
5. Re-run review committee with measurement evidence for signoff level ≥ 5

### Fabrication-real PCells

The `*_real` PCells add chip frames, keepout zones, wirebond pads, and
fabrication-real metadata to the base PCells.  They pass the layout reviewer's
`fabrication_real` mode check.

| PCell | Base | Adds |
|---|---|---|
| `cpw_resonator_real` | `cpw_quarter_wave_resonator` | Chip boundary, keepout corners, ground reference pads |
| `manhattan_jj_real` | `manhattan_josephson_junction` | Wirebond pads, via connections, keepout, shunt capacitor option |
| `squid_real` | `dc_squid_pair` | Flux-bias line, wirebond pads, keepout, shunt capacitor option |
| `via_chain_real` | `via_chain_monitor` | Four-terminal Kelvin pads, stage labels, keepout |

---

## 🔧 MCP tools

Start the local server: `uv run text-to-gds`. Public function count: **94**.

All-functions demo:

```bash
# List every public function and signature.
uv run python examples/run_function_demo.py list

# Execute one public function directly with JSON keyword arguments.
uv run python examples/run_function_demo.py compile_layout "{\"pcell\":\"manhattan_josephson_junction\",\"parameters\":{\"junction_width\":0.22,\"junction_height\":0.22},\"output_name\":\"demo_function_jj.gds\"}"

# Run the broad pass/fail smoke check across the public workflow surface.
uv run python scripts/smoke_check_functions.py
```

All 94 functions are importable directly from Python. The grouped examples below show the main function families in runnable contexts.

### Group 1 ??Core layout and graph IR (11 functions)

```python
from text_to_gds.server import (
    compile_layout, list_pcells, run_drc, run_process_drc,
    extract_layout, extract_physics_graph_artifact,
    generate_solver_inputs_from_physics_graph,
    generate_josephsoncircuits_model_from_physics_graph,
    extract_equivalent_circuit, run_lvs, generate_wafer_level_mask,
)

pcells = list_pcells()                                  # list all PCells
r = compile_layout("manhattan_josephson_junction",      # compile GDS + sidecar
                   output_name="jj.gds")
drc = run_drc(r["gds_path"], min_width_um=0.1)         # klayout DRC
ext = extract_layout(r["sidecar_path"])                 # extraction.json
graph = extract_physics_graph_artifact(r["sidecar_path"], output_name="jj")  # physics_graph.json
inputs = generate_solver_inputs_from_physics_graph(graph["result_path"])     # EM input files
jc = generate_josephsoncircuits_model_from_physics_graph(graph["result_path"])  # JC.jl model
```

**Full demo:** [`demo_B_full_extraction.py`](examples/demo_B_full_extraction.py)

---

### Group 2 ??0-to-100 compiler workflows (8 functions)

```python
from text_to_gds.server import (
    run_inverse_design_jpa, compare_measurement_engine,
    run_axion_search_jpa_final_test, plan_ljpa, plan_process_aware_jpa,
    run_design_workflow, run_optimized_design_workflow, run_ai_scientist,
)

plan = plan_ljpa(center_frequency_ghz=6.0, target_gain_db=20.0)
inv = run_inverse_design_jpa(target_frequency_ghz=6.0, target_gain_db=20.0)
axion = run_axion_search_jpa_final_test()
```

**Full demo:** `examples/zero_to_one_demos.py 60` and `100`

---

### Group 3 ??Backends and registries (13 functions)

```python
from text_to_gds.server import (
    list_professional_backends, run_backend_operation,
    list_simulators, list_research_integrations, list_fabrication_processes,
    list_process_design_kits, inspect_process_design_kit,
    list_improvement_functions, run_improvement_function,
    list_next_improvement_functions, run_next_improvement_function,
    list_third_wave_improvement_functions, run_third_wave_improvement_function,
)

backends = list_professional_backends()    # KQCircuits, gdsfactory, Qiskit Metal, local
sims = list_simulators()                   # JC.jl, scqubits, openEMS, Palace, Elmer, ...
pdks = list_process_design_kits()          # superconducting_al, nb_trilayer, ...
```

**Full demo:** `uv run python examples/05_backend_status_and_provenance.py`

---

### Group 4 ??EM and extraction solvers (23 functions)

```python
from text_to_gds.server import (
    export_openems_project, export_palace_project, export_elmer_project,
    export_fastcap, export_fasthenry, export_hfss_project, export_sonnet_project,
    export_mesh, export_3d_preview, export_cad_artifacts, export_rf_network,
    list_em_solvers, recommend_em_solver, cross_validate_solvers,
    export_open_eigenmode, extract_open_q3d, tune_idc_capacitance,
    route_open_solver, export_pyaedt_project, export_q3d_extract,
    recommend_pyaedt_design_correction, run_pyaedt_design_iteration,
    run_pyaedt_benchmarks,
)

r = compile_layout("cpw_quarter_wave_resonator",
                   parameters={"target_frequency_ghz": 6.0,
                               "effective_permittivity": 6.2,
                               "trace_width": 10.0, "gap": 6.0})
# openEMS FDTD handoff (sidecar as first arg)
em = export_openems_project(r["sidecar_path"])          # geometry.xml + mesh.xml
# Palace eigenmode handoff (GDS as first arg)
palace = export_palace_project(r["gds_path"], sidecar_path=r["sidecar_path"])
# FastCap capacitance handoff (GDS as first arg)
fc = export_fastcap(r["gds_path"])
# Cross-validate two sources
cv = cross_validate_solvers(
    [{"z0_ohm": 50.1, "method": "analytical"},
     {"z0_ohm": 49.8, "method": "extracted"}],
    quantity="z0_ohm", tolerance_pct=5.0)
```

**Full demo:** [`demo_E_full_pipeline_100.py`](examples/demo_E_full_pipeline_100.py)

---

### Group 5 ??Simulation, quantum, and measurement (22 functions)

```python
from text_to_gds.server import (
    run_simulation, export_hamiltonian_model, export_jpa_analysis,
    export_scientific_report, export_scientific_plot, export_measurement_plan,
    export_measurement_recipe, export_epr_analysis, export_superconducting_material,
    export_package_model, export_quantum_metal_bridge,
    fit_measurement, run_analytical_verification, record_experiment_feedback,
    run_traveling_wave_paper_benchmark, run_gaydamachenko_jtwpa_benchmark,
    run_paper_benchmarks, run_research_optimization, run_validation_checklist,
    run_parameter_sweep, run_uncertainty_analysis, analyze_cryostat_input_chain,
)

# scqubits Hamiltonian
sc = run_simulation(r["sidecar_path"], simulator="scqubits", jc_ua_per_um2=2.0)
# JosephsonCircuits.jl harmonic balance
jc = run_simulation(r["sidecar_path"], simulator="josephsoncircuits",
                    jc_ua_per_um2=2.0, target_frequency_ghz=6.0)
# Analytical theory cross-check
theory = run_analytical_verification(output_name="theory",
                                     center_frequency_ghz=6.0, kappa_mhz=120.0)
# 10-panel lineage report
report = export_scientific_report(r["sidecar_path"],
                                  gds_layout_png=r["screenshot_path"])
```

**Full demo:** [`demo_C_simulation_solvers.py`](examples/demo_C_simulation_solvers.py), [`demo_E_full_pipeline_100.py`](examples/demo_E_full_pipeline_100.py)

---

### Group 6 ??Review, constraints, data, and ML (16 functions)

```python
from text_to_gds.server import (
    review_layout, evaluate_signoff_level, validate_device_template,
    check_design_feasibility, check_physics_constraints, list_physics_templates,
    score_layout_quality, understand_layout, tokenize_layout,
    record_quantum_device, query_quantum_devices, export_device_training_data,
    run_open_benchmarks, predict_device_performance, list_quantum_devices,
    run_magic_extract,
)

import json
review = review_layout(r["sidecar_path"])              # 5-agent committee; score = min
signoff = evaluate_signoff_level(json.dumps({          # level 0??
    "extraction": ext, "drc": drc, "sidecar_path": r["sidecar_path"]}))
quality = score_layout_quality(r["sidecar_path"])      # overall quality score
feas = check_design_feasibility(                       # pre-screen before layout
    "jpa", json.dumps({"center_frequency_ghz": 6.0, "target_gain_db": 20.0}))
```

**Full demo:** [`demo_D_review_and_signoff.py`](examples/demo_D_review_and_signoff.py)

---

### All functions in one smoke check

```bash
# Runs all 93 functions end-to-end with pass/fail status
uv run python scripts/smoke_check_functions.py
```

All complete pipeline demos:

```bash
uv run python examples/demo_A_physics_gate.py      # 0??5
uv run python examples/demo_B_full_extraction.py   # 25??0
uv run python examples/demo_C_simulation_solvers.py # 50??5
uv run python examples/demo_D_review_and_signoff.py # 75??0
uv run python examples/demo_E_full_pipeline_100.py  # 90??00
uv run python examples/zero_to_one_demos.py all     # classic 6-level ladder
```

---
## ???Validity boundaries

Bundled PDK and process values are demonstration data. Publication or tapeout requires calibrated process data, extracted parasitics, mesh validation, and measured device data. Every reported value must carry `{value, unit, source, method, confidence}`.

---

## ????Contributing

Issues, PRs, PCell contributions, process-deck adapters, and solver adapters welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md).

## License

MIT. See [LICENSE](LICENSE).

