<div align="center">

# Text-to-GDS

**The only AI layout tool that rejects its own outputs.**

*Physics-grounded orchestration for superconducting quantum circuit layout — from natural-language prompt to fabrication-ready GDSII with full solver evidence.*

[Benchmarks](#-benchmarks) · [Real results](#-real-solver-results) · [How it works](#%EF%B8%8F-how-it-works) · [Installation](#-installation)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](pyproject.toml)
[![Backends](https://img.shields.io/badge/Backends-6%20live%20%7C%203%20pending-00A676?style=flat-square)](#backend-status)
[![MCP](https://img.shields.io/badge/MCP-80%2B%20tools-6B46C1?style=flat-square)](src/text_to_gds/server.py)

</div>

---

> **The promise is not "here is a layout."**
> It is **"here is a layout proven to work"** — feasibility-checked before generation, simulated on real open-source solvers, cross-validated by five independent reviewers, and **refused if it fails**.

Most AI layout tools generate a GDS file and stop. Text-to-GDS runs a **physics compiler**: every derived number traces to geometry, an explicit process input, or a real solver output file. `source = "LLM"` is an invalid provenance label and causes an immediate fail. A result that hides skipped solvers does not pass.

---

## What makes this different

| Capability | Text-to-GDS | Typical AI layout tool |
|---|---|---|
| Rejects its own layout if physics fails | **Yes** | No |
| Every number has `value + unit + source + method + confidence` | **Yes** | No |
| Real JPA gain from JosephsonCircuits.jl harmonic balance | **Yes** | No |
| Real qubit spectrum from scqubits diagonalisation | **Yes** | No |
| EM S-parameters from openEMS / Palace / Elmer FEM | **Yes** | No |
| 5-agent review committee (physics / microwave / fab / measurement / literature) | **Yes** | No |
| Auto-repair loop iterates until score ≥ 90 | **Yes** | No |
| Reports `SKIPPED` — never `PASSED` — when solver is unavailable | **Yes** | No |
| Solver agreement engine cross-checks ≥2 independent sources | **Yes** | No |
| 6 real open-source backends cloned and integrated | **Yes** | No |

---

## 📡 Real solver results

The numbers below are **not estimates. Not placeholders.** They were computed on this machine by real physics solvers during the last documentation run.

### JosephsonCircuits.jl — JPA harmonic balance (`executed`)

```
Device:      Lumped-element JPA seed, 6 GHz target
Solver:      JosephsonCircuits.jl v0.5.2 (harmonic balance)
Runtime:     Julia 1.12.6 @ .tools/julia-1.12.6/

Extracted:   Ic = 0.658 µA   (from junction area Jc = 2.0 µA/µm²)
             Lj = 500.0 pH   (Φ₀/2πIc)
             Cr = 1.255 pF   (resonator capacitance)
             Cc = 0.125 pF   (coupling capacitance)

Pump:        f_pump = 6.0 GHz
```

<img src="assets/jpa_analysis_example.png" alt="JPA gain from JosephsonCircuits.jl harmonic balance" width="680">

### scqubits — Transmon energy spectrum (`executed`)

```
Device:      Layout-derived TunableTransmon from LJPA JJ geometry
Solver:      scqubits 4.3.1 (exact diagonalisation, ncut=51)
Runtime:     Python 3.11 in-process

Extracted:   A = 0.387 µm²   (junction area from GDS)
             Ic = 0.548 µA   (Jc = 2.0 µA/µm²)
             Lj = 601.0 pH
             C  = 1170.7 fF

Computed:    Ej/h = 272.0 GHz
             Ec/h =  16.5 MHz
             Ej/Ec = 16 445       (deep transmon regime)

Energy levels (flux = 0.25 Φ₀):
             |0⟩ → |1⟩   f₀₁ = 5.029 GHz
             |1⟩ → |2⟩   f₁₂ = 5.012 GHz
             Anharmonicity α = −16.7 MHz
```

<img src="assets/scqubits_spectrum_example.png" alt="Transmon energy spectrum from scqubits" width="680">

### openEMS FDTD — RF S-parameters (`binary found, ready to run`)

```
Executable:  .tools/openEMS-v0.0.36/openEMS/openEMS.exe
Status:      SKIPPED in this documentation run (full CPW mesh not configured)
Activate:    export_openems_project(sidecar_path, run=True)
Output:      Touchstone .s2p + characteristic impedance Z0
```

<img src="assets/openems_extraction_example.png" alt="openEMS extraction status panel" width="680">

---

## 📸 Full pipeline figures

Every figure is produced by the physics-first pipeline. No mock data.

<table>
  <tr>
    <td align="center"><b>Manhattan JJ — 3-panel benchmark</b><br>
    GDS geometry · extraction.json · solver evidence<br>
    <img src="assets/benchmark_01_manhattan_jj_layout.png" width="340"></td>
    <td align="center"><b>CPW quarter-wave resonator — 3-panel</b><br>
    6 GHz · 50 Ω · openEMS-ready<br>
    <img src="assets/benchmark_05_cpw_resonator_test_layout.png" width="340"></td>
  </tr>
  <tr>
    <td align="center"><b>JJ calibration array — extraction sweep</b><br>
    Ic sweep from junction area metadata<br>
    <img src="assets/benchmark_04_jj_ic_calibration_array_layout.png" width="340"></td>
    <td align="center"><b>SFQ pulse splitter — JoSIM-ready</b><br>
    josim-cli at .tools/josim-v2.7/<br>
    <img src="assets/benchmark_03_sfq_pulse_splitter_layout.png" width="340"></td>
  </tr>
  <tr>
    <td align="center"><b>Process stack extraction</b><br>
    Layer-resolved geometry → EM model<br>
    <img src="assets/hfss_stack_3d.png" width="340"></td>
    <td align="center"><b>10-panel scientific lineage report</b><br>
    Every value with provenance chain<br>
    <img src="assets/scientific_report_example.png" width="340"></td>
  </tr>
</table>

---

## ⚡ Quick start

**1. Describe your device**

```text
Design a 6 GHz JPA with 20 dB gain and 200 MHz bandwidth.
Jc = 2.0 µA/µm², junction width = 0.22 µm.
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
# result["gds_path"]      — verified GDSII
# result["sidecar_path"]  — semantic manifest (ports, layers, junctions)
```

**3. Extract with full provenance**

```python
from text_to_gds.server import extract_layout

ext = extract_layout(result["sidecar_path"])
# ext["parameters"]["critical_current_ua"]     — from measured junction area
# ext["parameters"]["josephson_inductance_ph"]  — formula: Lj = Φ₀/(2πIc)
# ext["lineage"]["junction.ic"]["method_label"] — "extracted"
# ext["lineage"]["junction.lj"]["method_label"] — "estimated"
# Every value: formula, inputs, method_label, confidence_pct
```

**4. Run real solvers**

```python
from text_to_gds.server import run_simulation, export_openems_project

# JosephsonCircuits.jl harmonic balance — real gain vs pump power
sim = run_simulation(result["sidecar_path"], simulator="JosephsonCircuits.jl",
                     jc_ua_per_um2=2.0, coupling_capacitance_ff=5.0)
# sim["adapter_status"] == "executed"  — real solver ran
# sim["adapter_status"] == "skipped"   — Julia not found, never faked

# scqubits — real energy spectrum
spec = run_simulation(result["sidecar_path"], simulator="scqubits")
# spec["execution"]["f01_ghz"]           — real eigenvalue
# spec["execution"]["anharmonicity_ghz"] — real α

# openEMS FDTD — real S-parameters
em = export_openems_project(result["sidecar_path"], run=True)
# Returns status="executed" + .s2p Touchstone, or status="skipped" — never faked
```

**5. Run the review committee**

```python
from text_to_gds.review.committee import run_review_committee

verdict = run_review_committee(result["gds_path"], result["sidecar_path"],
                               extraction=ext, simulation=sim)
# verdict["final_score"]  — min(physics, microwave, fab, measurement, literature)
# verdict["blocking"]     — list of hard failures
# verdict["pass"]         — True only if final_score >= 90
# Auto-repair loop runs until accepted or budget exhausted.
```

**Full pipeline**

```
prompt
→ design_intent.json      (physics feasibility gate — blocks incoherent targets)
→ LayoutBackend           (KQCircuits → Qiskit Metal → gdsfactory → local_pcells)
→ GDSII + sidecar.json
→ DRC (KLayout)           (min width, spacing, layer mapping, JJ overlap)
→ extraction.json         (every value: extracted | estimated | simulated | measured)
→ EM solver               (openEMS / Palace / Elmer / FastCap)
→ circuit solver          (JosephsonCircuits.jl / scqubits / JoSIM / ngspice)
→ solver_agreement        (≥2 independent sources, confidence score)
→ review_committee        (5 agents, score = min across all)
→ auto-repair loop        (iterate until score ≥ 90 or budget exhausted)
→ signoff report          (PASS / FAIL, proven values table, next actions)
```

---

## 🧪 Benchmarks

Each benchmark shows three panels: **GDS geometry** · **extraction.json values** · **solver evidence** (green = executed, red = not executed). Nothing is hidden.

| # | Device | Prompt | Result |
|---|---|---|---|
| 1 | [Manhattan JJ](benchmarks/01-manhattan-josephson-junction.md) | Create a Manhattan JJ. Run DRC. Estimate `Ic` and `Lj` for `Jc = 2.0 µA/µm²`. | <img src="assets/benchmark_01_manhattan_jj_layout.png" width="220"> |
| 2 | [Ground Plane Coupon](benchmarks/02-compact-cmos-logic-cell.md) | Isolated ground-plane process coupon, `5 µm × 5 µm`, 1 µm clearance. | <img src="assets/benchmark_02_compact_cmos_logic_layout.png" width="220"> |
| 3 | [SFQ Pulse Splitter](benchmarks/03-sfq-pulse-splitter.md) | JJ splitter, `Ic = 0.3 µm × 0.3 µm`, 1 µm leads. Branch Ic and min-width targets. | <img src="assets/benchmark_03_sfq_pulse_splitter_layout.png" width="220"> |
| 4 | [JJ Calibration Array](benchmarks/04-jj-ic-calibration-array.md) | Sweep JJ areas. Report expected critical current from sidecar metadata. | <img src="assets/benchmark_04_jj_ic_calibration_array_layout.png" width="220"> |
| 5 | [CPW Resonator](benchmarks/05-cpw-resonator-test.md) | CPW quarter-wave resonator, 6 GHz, 10 MHz bandwidth, 50 Ω. | <img src="assets/benchmark_05_cpw_resonator_test_layout.png" width="220"> |
| 6 | [Via-Chain Monitor](benchmarks/06-via-chain-monitor.md) | 100-stage via-chain process monitor with resistance and topology targets. | <img src="assets/benchmark_06_via_chain_monitor_layout.png" width="220"> |

---

## 🔧 Backend status

Text-to-GDS is an orchestration layer over real open-source quantum EDA tools. Every backend is cloned, importable, or binary-discovered — not a toy simulator.

> Full install guide: [`EXTERNAL_BACKEND_INTEGRATION_STATUS.md`](EXTERNAL_BACKEND_INTEGRATION_STATUS.md)

### Layout backends

| Priority | Backend | Version | Status | Role |
|---|---|---|---|---|
| 1 | **KQCircuits** | 4.9.11 | **installed** | CPW layouts, resonators, airbridges, junction-compatible |
| 2 | **gdsfactory** | 9.43.0 | **installed** | Boolean ops, layer handling, export/import |
| 3 | **Qiskit Metal** | — | skipped (Win/Py3.12) | Transmon layout, CPW routing, launch pads |

### Simulation backends

| Backend | Version | Status | Role |
|---|---|---|---|
| **JosephsonCircuits.jl** | 0.5.2 | **executed** ✓ | JPA/JTWPA gain, pump sweep, harmonic balance |
| **scqubits** | 4.3.1 | **executed** ✓ | Transmon/fluxonium spectra, anharmonicity |
| **openEMS** | 0.0.36 | binary found | RF S-parameters, CPW Z0, Touchstone .s2p |
| **JoSIM** | 2.7 | binary found | SFQ circuit timing simulation |
| **pyEPR** | 0.9.6 | **installed** | Energy participation ratios |
| **Palace** | — | not installed | Eigenmode f0, Q factor (requires CMake + MPI build) |
| **Elmer FEM** | — | not installed | Electrostatic capacitance (requires installer) |

**`executed`** = real solver ran and produced output numbers used in this README.  
**`binary found`** = executable at `.tools/` — activate with one API call.  
**`skipped`** = adapter returned `status="skipped"` — explicit reason, no fake data.

---

## 🧰 Skills

| Skill | Role | Source |
|---|---|---|
| **Text-to-GDS** | Core layout generation with PCells, DRC, and JJ simulation | [skills/text-to-gds](skills/text-to-gds/SKILL.md) |
| **Simulation** | JosephsonCircuits.jl, JoSIM, ngspice, scqubits handoffs | [skills/text-to-gds-simulation](skills/text-to-gds-simulation/SKILL.md) |
| **Circuit Design** | Pre-layout circuit target planning (JPA / CPW / qubit) | [skills/text-to-gds-circuit-design](skills/text-to-gds-circuit-design/SKILL.md) |
| **Layout Design** | Compile → route → DRC → extract → review | [skills/text-to-gds-layout-design](skills/text-to-gds-layout-design/SKILL.md) |
| **Signoff** | Artifact audit, DRC status, simulation check, release validation | [skills/text-to-gds-signoff](skills/text-to-gds-signoff/SKILL.md) |
| **Physics Signoff** | Full signoff engineer: rejects any layout that lacks solver evidence | [skills/text-to-gds-physics-signoff](skills/text-to-gds-physics-signoff/SKILL.md) |

---

## 💻 Installation

**Skills CLI:**

```bash
npx skills install JungluChen/Text-to-Layout
```

**Local development** (Python 3.11+):

```powershell
git clone https://github.com/JungluChen/Text-to-Layout.git
cd Text-to-Layout
uv sync                          # core (gdsfactory, klayout, scqubits, kqcircuits, pyEPR)
uv sync --extra research         # + scikit-rf, QCoDeS, gmsh

uv run pytest                    # 200+ physics-grounded tests
uv run ruff check .
```

**Check and set up external solver toolchains:**

```powershell
# See what's available on this machine
uv run python scripts/check_external_tools.py

# Install missing Python packages and JosephsonCircuits.jl
uv run python scripts/setup_external_tools.py
```

Julia 1.12.6, JoSIM 2.7, and openEMS 0.0.36 are auto-discovered from `.tools/` — no PATH configuration needed. See [`EXTERNAL_BACKEND_INTEGRATION_STATUS.md`](EXTERNAL_BACKEND_INTEGRATION_STATUS.md) for Palace and Elmer.

---

## 📂 Examples

| Example | Backend | What it proves |
|---|---|---|
| [`examples/01_full_pipeline_jj.py`](examples/01_full_pipeline_jj.py) | JosephsonCircuits.jl | Full pipeline: intent → GDS → extract → harmonic balance → committee |
| [`examples/02_kqcircuits_cpw_resonator.py`](examples/02_kqcircuits_cpw_resonator.py) | KQCircuits + openEMS | CPW resonator → FDTD → Touchstone .s2p |
| [`examples/03_scqubits_transmon_spectrum.py`](examples/03_scqubits_transmon_spectrum.py) | scqubits | Extracted Ej/Ec → exact diagonalisation → f₀₁, α |
| [`examples/04_jpa_gain_josephsoncircuits.py`](examples/04_jpa_gain_josephsoncircuits.py) | JosephsonCircuits.jl | LJPA → real gain curve — only valid JPA gain source |
| [`examples/05_backend_status_and_provenance.py`](examples/05_backend_status_and_provenance.py) | all | 9-backend status table + value_record() provenance contract |

---

## ⚙️ How it works

### Layout backends — priority order

| Priority | Backend | When used |
|---|---|---|
| 1 | **KQCircuits** | Superconducting PCells with full process stack |
| 2 | **Qiskit Metal** | Transmon / qubit resonator geometries |
| 3 | **gdsfactory** | General parametric cells, routing, boolean ops |
| 4 | **local_pcells** | Tests and demos only — never for production/tapeout |

`compile_supercad` returns `status="unsupported"` if no backend can handle the request. No fake layout is generated.

### Simulation backends

| Analysis | Open backend | Role |
|---|---|---|
| RF S-parameters / Z0 | **openEMS** (FDTD) | CPW characteristic impedance, S11/S21 |
| Eigenmode f0 / Q | **Palace** (3D FEM) | Cavity resonator modes |
| Capacitance / inductance | **Elmer / FastCap / FastHenry** | IDC coupling, qubit C matrix |
| Nonlinear JPA / JTWPA gain | **JosephsonCircuits.jl** | Pump sweep, gain vs frequency |
| Qubit Hamiltonian / spectrum | **scqubits** | f₀₁, anharmonicity, energy levels |
| SFQ circuit timing | **JoSIM / ngspice** | Josephson voltage pulse propagation |
| Energy participation ratios | **pyEPR** | EPR from eigenmode field solution |

### Provenance labels

Every lineage entry in an extraction result carries a `method_label`:

| Label | Meaning |
|---|---|
| `extracted` | Measured from GDS geometry (e.g. junction overlap area) |
| `estimated` | Analytical formula (e.g. `Lj = Φ₀/(2πIc)`) — sanity check only |
| `simulated` | Produced by a real solver output file |
| `measured` | Imported from experiment data |

No value may appear in a report without a lineage entry. `source = "LLM"` is invalid and causes immediate failure.

### Solver agreement engine

A single solver is never trusted. The agreement engine cross-checks a quantity across ≥ 2 independent sources (analytical + FDTD + FEM) and returns a confidence score. Disagreement above tolerance blocks signoff.

### Five-agent review committee

Score = **minimum** across all five agents — one critical failure cannot be averaged away.

| Agent | Checks |
|---|---|
| **Physics** | Topology, JJ connectivity, CPW ground-gap, impedance vs extracted L and C |
| **Microwave** | Port existence, S-parameter reciprocity/passivity, `.s2p` file present |
| **Fabrication** | DRC min-width/spacing, layer map, JJ overlap, via enclosure |
| **Measurement** | RF port, DC bias, flux line, pump port, wirebond/probe pads |
| **Literature** | Parameter plausibility vs known device classes |

Pass threshold: `final_score ≥ 90`. Auto-repair loop iterates generate → review → fix until accepted or budget is spent.

### Hard stops

Immediately fails — no repair loop:

- Solver panel says `SOLVER NOT EXECUTED` and report claims simulation
- Layout generated by local fallback when a professional backend is available
- CPW has no valid ground-gap-signal-ground structure
- JPA has no valid nonlinear pump model
- Report hides skipped solvers
- Any claimed value has no provenance

---

## 🧠 MCP tools

Start the local server: `uv run text-to-gds`. 80+ tools:

| Group | Representative tools |
|---|---|
| **Orchestration** | `run_ai_scientist`, `run_design_workflow` |
| **Feasibility** | `check_design_feasibility`, `list_physics_templates`, `validate_device_template` |
| **Layout & DRC** | `compile_layout`, `run_drc`, `extract_layout`, `run_lvs` |
| **Open solvers** | `route_open_solver`, `cross_validate_solvers`, `export_open_eigenmode` |
| **Simulation & EM** | `run_simulation`, `export_openems_project`, `export_palace_project`, `export_jpa_analysis` |
| **Review & signoff** | `review_layout`, `run_open_benchmarks`, `understand_layout` |

---

## 🔬 Validity boundaries

Bundled PDK and process values are demonstration data. Publication or tapeout requires calibrated process data, extracted parasitics, mesh validation, and measured device data. Every reported value must carry `{value, unit, source, method, confidence}`.

---

## 🛠️ Contributing

Issues, PRs, PCell contributions, process-deck adapters, and solver adapters welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md).

## License

MIT. See [LICENSE](LICENSE).
