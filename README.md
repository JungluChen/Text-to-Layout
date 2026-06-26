<div align="center">

# Text-to-GDS

**Solver-first superconducting quantum layout automation.**

*Physics-grounded orchestration from a natural-language prompt to GDSII, extraction, solver inputs, review, and an explicit signoff status.*

[Quick start](#-quick-start) · [0-to-100 demos](#-0-to-100-demo-ladder) · [System functions](#-system-functions--worksteps) · [Backends](#-backend-status) · [Install](#-installation)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](pyproject.toml)
[![Backends](https://img.shields.io/badge/Backends-6%20live%20%7C%203%20pending-00A676?style=flat-square)](#-backend-status)
[![MCP](https://img.shields.io/badge/MCP-95%20tools-6B46C1?style=flat-square)](src/text_to_gds/server.py)

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

## The newest workflow

Every design request flows through these stages in order. Skipping a stage is a hard failure, not a warning.

```
prompt
  -> synthesize_design_intent()   physics feasibility gate; raises on incoherent targets
  -> compile_layout()             GDSII + sidecar.json (semantic manifest)
  -> run_drc()                    KLayout min-width / spacing / layer / JJ-overlap
  -> extract_layout()             extraction.json, lineage on every value
  -> extract_physics_graph()      physics_graph.json compiler IR (GDS no longer the source of truth)
  -> generate_solver_inputs()     openEMS / Palace / Elmer input files from the graph
  -> run_simulation()             real solver output OR status="skipped" (never faked)
  -> cross_validate_solvers()     agreement engine across >= 2 independent sources
  -> golden_compare()             generated device vs cited literature templates
  -> review_layout()              5-agent committee, score = min across all agents
  -> evaluate_signoff_level()     level 0-6, PASS only when score >= 90
  -> export_scientific_report()   lineage report + Generated vs Reference panel
```

Three rules are enforced at every stage:

1. `source = "LLM"` in any provenance record -> immediate review failure.
2. `status = "skipped"` when a solver is unavailable -> never `"passed"` or `"success"`.
3. Literature agreement is claimed only when extracted/generated parameters match cited reference values.
4. Review committee score = **minimum** across all reviewers -> one critical failure cannot be averaged away.

---

## 🚀 Quick start

**1. Describe your device**

```text
Design a 6 GHz JPA with 20 dB gain and 200 MHz bandwidth.
Jc = 2.0 uA/um^2, junction width = 0.22 um.
Include flux line, pump port, and wirebond pads.
```

**2. Compile through the physics gate**

```python
from text_to_gds.design_intent import synthesize_design_intent
from text_to_gds.server import compile_layout

intent = synthesize_design_intent(
    "Design a 6 GHz JPA with 20 dB gain and 200 MHz bandwidth",
    inputs={"device": "JPA", "frequency_ghz": 6.0, "gain_db": 20.0,
            "bandwidth_mhz": 200.0, "jc_ua_per_um2": 2.0},
)
# Raises immediately if targets are physically inconsistent.
# No layout is generated from an incoherent design intent.

result = compile_layout(pcell="lumped_element_jpa_seed",
                        parameters={"center_frequency_ghz": 6.0, "target_gain_db": 20.0})
# result["gds_path"]      -> verified GDSII
# result["sidecar_path"]  -> semantic manifest (ports, layers, junctions)
```

**3. Extract with full provenance**

```python
from text_to_gds.server import extract_layout, extract_physics_graph_artifact

ext   = extract_layout(result["sidecar_path"], jc_ua_per_um2=2.0)
graph = extract_physics_graph_artifact(result["sidecar_path"], jc_ua_per_um2=2.0)
# ext["result_path"]    -> extraction.json summary
# graph["result_path"]  -> physics_graph.json compiler IR
# graph["nodes"]        -> conductor, capacitor, inductor, JJ, CPW, port, ground
# graph["edges"]        -> electrical, capacitive, mutual, microwave-port relations
```

**4. Run real solvers**

```python
from text_to_gds.server import run_simulation, export_openems_project

# scqubits -> real energy spectrum
sc = run_simulation(result["sidecar_path"], simulator="scqubits", jc_ua_per_um2=2.0)
# JosephsonCircuits.jl -> real gain vs pump power
jc = run_simulation(result["sidecar_path"], simulator="josephsoncircuits",
                    jc_ua_per_um2=2.0, target_frequency_ghz=6.0)
# openEMS FDTD -> real S-parameters, or status="skipped" -- never faked
em = export_openems_project(result["sidecar_path"], run=True)
```

**5. Review and sign off**

```python
from text_to_gds.server import review_layout, evaluate_signoff_level
import json

review  = review_layout(result["sidecar_path"])              # score = min(5 agents)
signoff = evaluate_signoff_level(json.dumps({                # level 0-6
    "extraction": ext, "physics_graph": graph,
    "sidecar_path": result["sidecar_path"]}))
# review["approved"] is True only when score >= 90.
```

**6. Compare against literature references**

```python
from text_to_gds.server import golden_compare
from pathlib import Path
import json

sidecar = json.loads(Path(result["sidecar_path"]).read_text(encoding="utf-8"))

comparison = golden_compare(
    {"pcell": sidecar["pcell"], "info": sidecar["info"]},
    "jpa",
)
# comparison["topology_score"]       -> required topology feature coverage
# comparison["parameter_error"]      -> generated vs cited reference values
# comparison["missing_features"]     -> no silent fill-in for absent evidence
# comparison["fabrication_warnings"] -> process/topology warnings
# comparison["literature_distance"]  -> aggregate distance, not a signoff claim
```

---

## 🪜 0-to-100 demo ladder

Five runnable demos cover the newest workflow end to end. Each file is self-contained, prints every workstep, and ends with an explicit `[PASS]` line. Screenshots are secondary — acceptance comes from GDS polygons, boolean extraction, provenance records, solver status, and validation output.

```bash
uv run python examples/demo_A_physics_gate.py       # 0  -> 25
uv run python examples/demo_B_full_extraction.py    # 25 -> 50
uv run python examples/demo_C_simulation_solvers.py # 50 -> 75
uv run python examples/demo_D_review_and_signoff.py # 75 -> 90
uv run python examples/demo_E_full_pipeline_100.py  # 90 -> 100
```

### Demo A — Physics feasibility gate (0 → 25)

[`examples/demo_A_physics_gate.py`](examples/demo_A_physics_gate.py) — proves incoherent targets are blocked before any GDS is written.

| Step | Function | Workstep |
|---|---|---|
| 1 | `check_design_feasibility` | Quick pre-screen of a JPA target (6 GHz, 20 dB, 200 MHz). |
| 2 | `synthesize_design_intent` | Physics gate. Derives `Ic`, `Lj`, `Z0`; raises if targets are inconsistent. |
| 3 | `compile_layout` | Reached only when intent status is `ready`; writes GDS + sidecar. |

```text
Step 2 -- synthesize_design_intent (physics gate)
  status:  ready
  Ic:      0.1936 uA      Lj: 1699.93 pH      Z0: 50.94 ohm
Step 3 -- compile_layout (gated by design intent) -> status: compiled
[PASS] Physics gate verified: incoherent designs are blocked before layout.
```

### Demo B — Full extraction pipeline (25 → 50)

[`examples/demo_B_full_extraction.py`](examples/demo_B_full_extraction.py) — GDS → DRC → extraction.json → physics_graph.json → solver inputs, with provenance on every value.

| Step | Function | Workstep |
|---|---|---|
| 1 | `compile_layout` | CPW quarter-wave resonator (6 GHz, 50 Ω). |
| 2 | `run_drc` | KLayout min-width / spacing; reports `checked_shapes` and `violations`. |
| 3 | `extract_layout` | extraction.json with `method_label` + `source` + `confidence` per value. |
| 4 | `extract_physics_graph_artifact` | physics_graph.json compiler IR (10 nodes / 29 edges). |
| 5 | `generate_solver_inputs_from_physics_graph` | openEMS `geometry/mesh/ports` XML, Palace config, Elmer `geo/msh/sif`. |

```text
Step 2 -- run_drc -> status: passed, checked_shapes: 25, violations: 0
Step 4 -- physics-graph.v1 -> node count: 10, edge count: 29
Step 5 -- openEMS: ['geometry_xml','mesh_xml','ports_xml']  palace: ['config_json']  elmer: ['geo','msh','sif']
[PASS] GDS -> DRC -> extraction -> physics_graph -> solver inputs
```

### Demo C — Simulation solvers (50 → 75)

[`examples/demo_C_simulation_solvers.py`](examples/demo_C_simulation_solvers.py) — real solver handoffs with honest status reporting.

| Step | Function | Workstep |
|---|---|---|
| 1 | `compile_layout` | Lumped-element JPA seed layout. |
| 2 | `run_simulation` (scqubits) | Hamiltonian, `f01`, anharmonicity. |
| 3 | `run_simulation` (josephsoncircuits) | Harmonic-balance gain vs pump power. |
| 4 | `export_hamiltonian_model` | scqubits Hamiltonian handoff file. |
| 5 | `generate_josephsoncircuits_model_from_physics_graph` | JC.jl model from the graph. |
| 6 | `run_analytical_verification` + `cross_validate_solvers` | Analytical cross-check across two independent sources. |

`status="executed"` appears only when a real output file exists; otherwise `status="skipped"` with an explicit reason.

### Demo D — Review committee + signoff (75 → 90)

[`examples/demo_D_review_and_signoff.py`](examples/demo_D_review_and_signoff.py) — 5-agent committee and signoff-level evaluation.

| Step | Function | Workstep |
|---|---|---|
| 1 | `compile_layout` + `extract_layout` | Build and extract the candidate. |
| 2 | `review_layout` | physics / microwave / fab / measurement / literature; **score = min**. |
| 3 | `evaluate_signoff_level` | Level 0-6 determination (0 = geometry, 5 = physics, 6 = measured). |
| 4 | `validate_device_template` | Schema validation. |
| 5 | `export_measurement_plan` | What to measure to reach level 6. |

```text
Step 2 -- review_layout -> score: 10 (min across all 5 reviewers), approved: False
Step 3 -- evaluate_signoff_level -> level: 0 -- blocked
[PASS] Review committee + signoff verified.
```

### Demo E — Full 100-level pipeline (90 → 100)

[`examples/demo_E_full_pipeline_100.py`](examples/demo_E_full_pipeline_100.py) — the complete 13-step orchestration from prompt to a signoff-ready bundle.

| Steps | Functions | Workstep |
|---|---|---|
| 1-4 | `compile_layout`, `run_drc`, `extract_layout`, `extract_physics_graph_artifact`, `generate_solver_inputs_from_physics_graph` | Layout → DRC → extraction → graph → solver inputs. |
| 5 | `export_openems_project`, `export_palace_project` | EM solver handoffs (skip cleanly if Octave/Palace absent). |
| 6 | `run_simulation` (scqubits + josephsoncircuits) | Circuit/qubit solvers. |
| 7 | `run_analytical_verification`, `cross_validate_solvers` | Theory cross-check + agreement engine. |
| 8 | `golden_compare` | Literature-backed comparison against cited transmon/JPA/process/CPW templates. |
| 9-10 | `review_layout`, `evaluate_signoff_level` | Committee verdict + signoff level. |
| 11-14 | `score_layout_quality`, `export_jpa_analysis`, `export_scientific_report`, `export_measurement_recipe` | Quality score, JPA analysis, lineage report with Generated vs Reference panel, VNA recipe for level 6. |

**Run the whole ladder, plus the classic 6-level demos:**

```bash
uv run python examples/demo_A_physics_gate.py
uv run python examples/demo_B_full_extraction.py
uv run python examples/demo_C_simulation_solvers.py
uv run python examples/demo_D_review_and_signoff.py
uv run python examples/demo_E_full_pipeline_100.py
uv run python examples/zero_to_one_demos.py all     # classic 6-level ladder (0,20,40,60,80,100)
```

| Level | Classic demo | Newest-workflow coverage |
|---:|---|---|
| 0 | `zero_to_one_demos.py 0` | Lists PCells, process kits, and EM solvers before layout. |
| 20 | `zero_to_one_demos.py 20` | Manhattan JJ GDS, DRC, boolean overlap `JJ/M1/M2`, extraction + physics graph. |
| 40 | `zero_to_one_demos.py 40` | CPW resonator, subtractive ground clearances, EM solver input files. |
| 60 | `zero_to_one_demos.py 60` | `run_inverse_design_jpa` — every optimizer candidate regenerates GDS before scoring. |
| 80 | `zero_to_one_demos.py 80` | `compare_measurement_engine` — VNA-style CSV fit and process correction. |
| 100 | `zero_to_one_demos.py 100` | `run_axion_search_jpa_final_test` — GDS + graph + extracted LC + EM inputs + JC.jl handoff + gain map. |

---

## 🧩 System functions & worksteps

Start the local MCP server with `uv run text-to-gds`. The public surface is **95 MCP tool functions**, all importable directly from Python (`from text_to_gds.server import ...`) and all exposed as `@mcp.tool()`. In addition, module-level functions live in deeper packages for direct use.

```bash
# List every public function and signature.
uv run python examples/run_function_demo.py list

# Execute one public function directly with JSON keyword arguments.
uv run python examples/run_function_demo.py compile_layout \
  "{\"pcell\":\"manhattan_josephson_junction\",\"parameters\":{\"junction_width\":0.22,\"junction_height\":0.22},\"output_name\":\"demo_function_jj.gds\"}"

# Run the broad pass/fail smoke check across the public workflow surface.
uv run python scripts/smoke_check_functions.py
```

### Group 1 — Core layout and graph IR (11 functions)

```python
from text_to_gds.server import (
    compile_layout, list_pcells, run_drc, run_process_drc,
    extract_layout, extract_physics_graph_artifact,
    generate_solver_inputs_from_physics_graph,
    generate_josephsoncircuits_model_from_physics_graph,
    extract_equivalent_circuit, run_lvs, generate_wafer_level_mask,
)

pcells = list_pcells()                                    # all PCells
r      = compile_layout("manhattan_josephson_junction", output_name="jj.gds")
drc    = run_drc(r["gds_path"], min_width_um=0.1)         # KLayout DRC
ext    = extract_layout(r["sidecar_path"])                # extraction.json
graph  = extract_physics_graph_artifact(r["sidecar_path"], output_name="jj")  # physics_graph.json
inputs = generate_solver_inputs_from_physics_graph(graph["result_path"])      # EM input files
jc     = generate_josephsoncircuits_model_from_physics_graph(graph["result_path"])  # JC.jl model
```

### Group 2 — 0-to-100 compiler workflows (8 functions)

```python
from text_to_gds.server import (
    run_inverse_design_jpa, compare_measurement_engine,
    run_axion_search_jpa_final_test, plan_ljpa, plan_process_aware_jpa,
    run_design_workflow, run_optimized_design_workflow, run_ai_scientist,
)

plan  = plan_ljpa(center_frequency_ghz=6.0, target_gain_db=20.0)
inv   = run_inverse_design_jpa(target_frequency_ghz=6.0, target_gain_db=20.0)
axion = run_axion_search_jpa_final_test()
```

### Group 3 — Backends and registries (13 functions)

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
sims     = list_simulators()               # JC.jl, scqubits, openEMS, Palace, Elmer, ...
pdks     = list_process_design_kits()      # superconducting_al, nb_trilayer, ...
```

### Group 4 — EM and extraction solvers (23 functions)

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

em     = export_openems_project(r["sidecar_path"])                         # geometry.xml + mesh.xml
palace = export_palace_project(r["gds_path"], sidecar_path=r["sidecar_path"])
cv     = cross_validate_solvers(                                           # >= 2 sources
    [{"z0_ohm": 50.1, "method": "analytical"}, {"z0_ohm": 49.8, "method": "extracted"}],
    quantity="z0_ohm", tolerance_pct=5.0)
```

### Group 5 — Simulation, quantum, literature, and measurement

```python
from text_to_gds.server import (
    run_simulation, export_hamiltonian_model, export_jpa_analysis,
    export_scientific_report, export_scientific_plot, export_measurement_plan,
    export_measurement_recipe, export_epr_analysis, export_superconducting_material,
    export_package_model, export_quantum_metal_bridge,
    golden_compare,
    fit_measurement, run_analytical_verification, record_experiment_feedback,
    run_traveling_wave_paper_benchmark, run_gaydamachenko_jtwpa_benchmark,
    run_paper_benchmarks, run_research_optimization, run_validation_checklist,
    run_parameter_sweep, run_uncertainty_analysis, analyze_cryostat_input_chain,
)

sc     = run_simulation(r["sidecar_path"], simulator="scqubits", jc_ua_per_um2=2.0)
jc     = run_simulation(r["sidecar_path"], simulator="josephsoncircuits",
                        jc_ua_per_um2=2.0, target_frequency_ghz=6.0)
theory = run_analytical_verification(output_name="theory",
                                     center_frequency_ghz=6.0, kappa_mhz=120.0)
report = export_scientific_report(r["sidecar_path"], gds_layout_png=r["screenshot_path"])
lit    = golden_compare(r["sidecar_path"], "jpa")
```

### Group 6 — Review, constraints, data, and ML (16 functions)

```python
from text_to_gds.server import (
    review_layout, evaluate_signoff_level, validate_device_template,
    check_design_feasibility, check_physics_constraints, list_physics_templates,
    score_layout_quality, understand_layout, tokenize_layout,
    record_quantum_device, query_quantum_devices, export_device_training_data,
    run_open_benchmarks, predict_device_performance, list_quantum_devices,
    run_magic_extract,
)

review  = review_layout(r["sidecar_path"])                 # 5-agent committee; score = min
signoff = evaluate_signoff_level(json.dumps({              # level 0-6
    "extraction": ext, "drc": drc, "sidecar_path": r["sidecar_path"]}))
quality = score_layout_quality(r["sidecar_path"])          # overall quality score
feas    = check_design_feasibility(                        # pre-screen before layout
    "jpa", json.dumps({"center_frequency_ghz": 6.0, "target_gain_db": 20.0}))
```

### All functions in one smoke check

```bash
# Runs the public workflow surface end-to-end with pass/fail status.
uv run python scripts/smoke_check_functions.py
```

---

## 📦 Module-level API reference

These functions live outside `server.py` and are used directly by the examples and internal pipeline.

### Signoff and evidence (`signoff.py`, `signoff_extraction.py`, `fabrication_signoff.py`, `evidence.py`)

| Function | Module | Description |
|---|---|---|
| `evaluate_signoff(evidence)` | `signoff.py` | Evaluate signoff Level 0–6 from explicit artifacts |
| `validate_value_record(record)` | `signoff.py` | Validate a physical value record (rejects `source="LLM"`) |
| `validate_value_records(records)` | `signoff.py` | Batch-validate value records |
| `extract_capacitance(gds, out, stem, ...)` | `signoff_extraction.py` | FastCap2/Elmer electrostatic capacitance (runs if available) |
| `extract_sparameters(out, stem, ...)` | `signoff_extraction.py` | openEMS/Palace CPW S-parameters (runs if available) |
| `extract_jpa_dynamics(device, out, stem, ...)` | `signoff_extraction.py` | JosephsonCircuits.jl JPA gain/noise/QE (runs if Julia available) |
| `signoff_drc(path)` | `fabrication_signoff.py` | Real KLayout DRC: width/space/JJ/via-enclosure checks |
| `signoff_lvs(path)` | `fabrication_signoff.py` | Geometry-extracted LVS from connectivity graph |
| `floating_metal_report(path)` | `fabrication_signoff.py` | Floating metal island detection with area calculation |
| `layer_connectivity_report(path)` | `fabrication_signoff.py` | Via/metal layer connectivity graph with area totals |
| `pdk_rule_summary()` | `fabrication_signoff.py` | PDK fabrication rule set as JSON |
| `write_klayout_lyp(path)` | `fabrication_signoff.py` | KLayout layer-properties XML file |
| `run_fabrication_signoff(gds, out, stem)` | `fabrication_signoff.py` | Full signoff bundle: DRC + LVS + floating metal + connectivity + rules + .lyp |
| `solver_evidence(...)` | `evidence.py` | Build one provenance record for a solver quantity |
| `evidence_bundle(device, ...)` | `evidence.py` | Assemble per-quantity records plus skipped/executed summary |

### Design intent and physics graph (`design_intent.py`, `physics_graph.py`)

| Function | Module | Description |
|---|---|---|
| `synthesize_design_intent(prompt, inputs=...)` | `design_intent.py` | Parse requirements and solve pre-layout circuit quantities |
| `write_design_intent(intent, path)` | `design_intent.py` | Write design intent JSON |
| `extract_physics_graph(gds, sidecar, ...)` | `physics_graph.py` | Extract physics_graph.json compiler IR from GDS polygons |
| `graph_to_josephsoncircuits_model(graph)` | `physics_graph.py` | Convert physics graph to JosephsonCircuits.jl circuit model |

### Device views (`device_views.py`)

| Function | Module | Description |
|---|---|---|
| `render_device_views(gds, out, stem, ...)` | `device_views.py` | Render all 4 views (mask, layer, net, circuit) |
| `render_mask_view(polys, bounds, path, title)` | `device_views.py` | True-polarity signoff mask (opaque = superconductor) |
| `render_layer_view(polys, bounds, path, ...)` | `device_views.py` | Layer-coloured view with legend outside geometry |
| `render_net_view(polys, bounds, conn, ...)` | `device_views.py` | Extracted electrical nets, role-coloured |
| `render_evidence_view(bundle, path, title)` | `device_views.py` | Tabular provenance view with source/provenance column |

### Verification (`verification/`)

| Function | Module | Description |
|---|---|---|
| `extract_connectivity(path)` | `connectivity.py` | GDS-derived physical connectivity (nodes, edges, topology) |
| `run_drc(path)` | `drc.py` | Minimal polygon-level DRC (known layers, JJ bbox) |
| `generate_lvs_report(gds, out, stem)` | `lvs.py` | Full LVS: graph + overlay + schematic + JSON report |

### Layout validation (`layout_validator.py`)

| Function | Module | Description |
|---|---|---|
| `validate_layout(gds, sidecar, ...)` | `layout_validator.py` | 8 geometry checks: basic, width, JJ, CPW, JPA, resonator, via, ports |
| `validate_against_golden(gds, expected)` | `layout_validator.py` | Validate against golden expected.json reference |

### Literature references (`reference_compare.py`)

| Function | Module | Description |
|---|---|---|
| `golden_compare(device, reference)` | `reference_compare.py` | Compare generated/extracted device data against cited golden templates |
| `load_golden_reference(reference)` | `reference_compare.py` | Load or merge JSON references from `references/` |
| `default_references(device_family)` | `reference_compare.py` | Resolve `transmon`, `jpa`, `process`, or `cpw` aliases |
| `write_golden_comparison(device, reference, output)` | `reference_compare.py` | Write a comparison report JSON |
| `compare_cpw_against_references(project_root, output_dir)` | `reference_compare.py` | Compare CPW synthesis metadata against cloned backend source references |

### Auto-repair and agreement (`auto_repair.py`, `solver_agreement.py`, `artifact_validator.py`)

| Function | Module | Description |
|---|---|---|
| `run_auto_repair(initial, gen, repair, ...)` | `auto_repair.py` | Bounded generate → review → fix loop (max 6 iterations) |
| `cross_validate(sources, quantity, ...)` | `solver_agreement.py` | Cross-validate one quantity across independent sources |
| `cross_validate_solvers(sources, ...)` | `solver_agreement.py` | Cross-validate two Touchstone files |
| `validate_artifact(solver, result, ...)` | `artifact_validator.py` | Validate solver artifact (gain array, s2p, cap matrix) |
| `validate_all_artifacts(results, ...)` | `artifact_validator.py` | Validate all solver artifacts in a results dict |

### Physics (`physics/cpw.py`, `physics/jj.py`, `physics/resonator.py`)

| Function | Module | Description |
|---|---|---|
| `z0_cpw(center_width_um, gap_um, ...)` | `cpw.py` | Characteristic impedance Z0 of a CPW |
| `epsilon_eff_cpw(...)` | `cpw.py` | Effective permittivity of a CPW on finite substrate |
| `phase_velocity_m_per_s(eps_eff)` | `cpw.py` | Phase velocity vp = c / sqrt(eps_eff) |
| `capacitance_per_length_f_per_m(z0, eps)` | `cpw.py` | Distributed capacitance C' |
| `inductance_per_length_h_per_m(z0, eps)` | `cpw.py` | Distributed inductance L' |
| `kinetic_inductance_per_length_h_per_m(...)` | `cpw.py` | Kinetic inductance per unit length |
| `quarter_wave_length_um(freq, eps)` | `cpw.py` | Physical length for lambda/4 resonator |
| `full_cpw_analysis(...)` | `cpw.py` | Complete CPW parameter extraction |
| `ic_from_area(area, jc)` | `jj.py` | Critical current Ic = Jc * A |
| `lj_from_ic(ic)` | `jj.py` | Josephson inductance Lj = Phi0 / (2*pi*Ic) |
| `ej_from_ic(ic)` | `jj.py` | Josephson energy Ej = hbar*Ic/(2e) |
| `ec_from_capacitance(c)` | `jj.py` | Charging energy Ec = e^2/(2C) |
| `transmon_f01_hz(ej, ec)` | `jj.py` | Transmon f01 from Ej and Ec |
| `transmon_anharmonicity_hz(ec)` | `jj.py` | Transmon anharmonicity alpha = -Ec |
| `full_jj_analysis(area, jc, ...)` | `jj.py` | Complete JJ parameter extraction |
| `quarter_wave_frequency_ghz(length, eps)` | `resonator.py` | Resonant frequency of lambda/4 CPW resonator |
| `loaded_q(qi, qc)` | `resonator.py` | Loaded Q: 1/Ql = 1/Qi + 1/Qc |
| `extract_q_from_s21(freqs, s21)` | `resonator.py` | Khalil circle fit Q extraction from S21 |
| `full_resonator_analysis(...)` | `resonator.py` | Complete resonator characterization |

### Core utilities (`core/units.py`, `core/provenance.py`)

| Function | Module | Description |
|---|---|---|
| `Quantity(value, unit, source)` | `units.py` | Physical quantity with provenance (rejects `source="LLM"`) |
| `ghz_to_hz`, `hz_to_ghz`, `um_to_m`, `pf_to_f`, etc. | `units.py` | 16 unit conversion functions |
| `SPEED_OF_LIGHT`, `PLANCK_H`, `ELECTRON_CHARGE`, etc. | `units.py` | 10 CODATA 2019 physical constants |
| `provenance_record(value, unit, source, ...)` | `provenance.py` | Factory for ProvenanceRecord with path normalization |
| `write_provenance_bundle(records, path)` | `provenance.py` | Write named ProvenanceRecords to JSON |

### Geometry (`geometry/polygon.py`, `geometry/boolean.py`, `geometry/extraction.py`)

| Function | Module | Description |
|---|---|---|
| `load_layout(path)` | `polygon.py` | Load GDS into klayout Layout + top cell |
| `layer_regions(path)` | `polygon.py` | Extract merged regions keyed by (layer, datatype) |
| `merge`, `overlap`, `inside`, `interacting` | `boolean.py` | KLayout Region boolean operations |
| `extract_layer_features(gds)` | `extraction.py` | Bounding boxes, areas, port markers per layer |

### Device library (`device_library.py`)

| Class | Description |
|---|---|
| `JPA(frequency_ghz, impedance_ohm, target_gain_db, bandwidth_mhz)` | Josephson parametric amplifier device |
| `Transmon(frequency_ghz, anharmonicity_mhz)` | Transmon qubit device |
| `Resonator(frequency_ghz, impedance_ohm)` | CPW quarter-wave resonator device |
| `CalibrationJJArray(sizes)` | JJ calibration array for Ic sweep |
| `TWPA(frequency_ghz, target_gain_db)` | Traveling-wave parametric amplifier |

Each device exposes `.geometry()`, `.extract()`, `.ports()`, `._synthesis()`, and `._plan()` methods.

---

## 📊 Real solver results

A solver counts as **executed** only when a solver-owned output file exists.

### JosephsonCircuits.jl — JPA harmonic balance (`executed`)

```
Device:    Lumped-element JPA seed, 6 GHz target
Solver:    JosephsonCircuits.jl v0.5.2 (harmonic balance)
Runtime:   Julia 1.12.6 @ .tools/julia-1.12.6/
Extracted: Ic = 0.658 uA (junction area, Jc = 2.0 uA/um^2)
           Lj = 500.0 pH    Cr = 1.255 pF    Cc = 0.125 pF
Pump:      f_pump = 6.0 GHz
```

<img src="assets/jpa_analysis_example.png" alt="JPA gain from JosephsonCircuits.jl harmonic balance" width="680">

### scqubits — Transmon energy spectrum (`executed`)

```
Device:    Layout-derived TunableTransmon from JPA JJ geometry
Solver:    scqubits 4.3.1 (exact diagonalisation, ncut=51)
Computed:  Ej/h = 272.0 GHz    Ec/h = 16.5 MHz    Ej/Ec = 16445 (deep transmon)
           f01 = 5.029 GHz     Anharmonicity = -16.7 MHz (flux = 0.25 Phi0)
```

<img src="assets/scqubits_spectrum_example.png" alt="Transmon energy spectrum from scqubits" width="680">

### openEMS FDTD — RF S-parameters (`binary found, ready to run`)

```
Executable: .tools/openEMS-v0.0.36/openEMS/openEMS.exe
Status:     SKIPPED in the documentation run (Octave post-processor not configured)
Activate:   export_openems_project(sidecar_path, run=True)
Output:     Touchstone .s2p + characteristic impedance Z0
```

<img src="assets/openems_extraction_example.png" alt="openEMS extraction status panel" width="680">

---

## 🖼️ Full pipeline figures

Every figure is produced by the physics-first pipeline. Solver panels show **EXECUTED** (green), **SKIPPED** (grey), or **FAILED** (red). A skipped solver means the binary was unavailable during the documentation run — not a failure, but not evidence either.

Regenerate all README and guide assets with:

```bash
uv run python scripts/generate_assets.py all
uv run python scripts/run_benchmarks.py
uv run python scripts/render_reports.py
```

<table>
  <tr>
    <td align="center"><b>Manhattan JJ — 3-panel benchmark</b><br>
    GDS geometry -> extraction.json -> solver evidence<br>
    <img src="assets/benchmark_01_manhattan_jj_layout.png" width="340"></td>
    <td align="center"><b>CPW quarter-wave resonator — 3-panel</b><br>
    6 GHz, 50 ohm, openEMS-ready<br>
    <img src="assets/benchmark_05_cpw_resonator_test_layout.png" width="340"></td>
  </tr>
  <tr>
    <td align="center"><b>JJ calibration array — extraction sweep</b><br>
    Ic sweep from junction-area metadata<br>
    <img src="assets/benchmark_04_jj_ic_calibration_array_layout.png" width="340"></td>
    <td align="center"><b>SFQ pulse splitter — JoSIM-ready</b><br>
    josim-cli at .tools/josim-v2.7/<br>
    <img src="assets/benchmark_03_sfq_pulse_splitter_layout.png" width="340"></td>
  </tr>
  <tr>
    <td align="center"><b>Process stack extraction</b><br>
    Layer-resolved geometry -> EM model<br>
    <img src="assets/hfss_stack_3d.png" width="340"></td>
    <td align="center"><b>Scientific lineage report</b><br>
    Provenance + Generated vs Reference panel<br>
    <img src="assets/scientific_report_example.png" width="340"></td>
  </tr>
</table>

---

## 🏁 Benchmarks

The `*_layout.png` assets are geometry-only layout thumbnails. Solver/status panels are generated separately as `*_benchmark.png` so layout assets are never overwritten by report graphics.

| # | Device | Prompt | Result |
|---|---|---|---|
| 1 | [Manhattan JJ](benchmarks/01-manhattan-josephson-junction.md) | Create a Manhattan JJ. Run DRC. Estimate `Ic` and `Lj` for `Jc = 2.0 uA/um^2`. | <img src="assets/benchmark_01_manhattan_jj_layout.png" width="220"> |
| 2 | [Ground Plane Coupon](benchmarks/02-compact-cmos-logic-cell.md) | Isolated ground-plane process coupon, 5 um x 5 um, 1 um clearance. | <img src="assets/benchmark_02_compact_cmos_logic_layout.png" width="220"> |
| 3 | [SFQ Pulse Splitter](benchmarks/03-sfq-pulse-splitter.md) | JJ splitter, `Ic = 0.3 uA + 0.3 uA`, 1 um leads. | <img src="assets/benchmark_03_sfq_pulse_splitter_layout.png" width="220"> |
| 4 | [JJ Calibration Array](benchmarks/04-jj-ic-calibration-array.md) | Sweep JJ areas; report expected Ic from sidecar metadata. | <img src="assets/benchmark_04_jj_ic_calibration_array_layout.png" width="220"> |
| 5 | [CPW Resonator](benchmarks/05-cpw-resonator-test.md) | CPW quarter-wave resonator, 6 GHz, 10 MHz bandwidth, 50 ohm. | <img src="assets/benchmark_05_cpw_resonator_test_layout.png" width="220"> |
| 6 | [Via-Chain Monitor](benchmarks/06-via-chain-monitor.md) | 100-stage via-chain process monitor with resistance and topology targets. | <img src="assets/benchmark_06_via_chain_monitor_layout.png" width="220"> |

---

## 🔌 Backend status

Text-to-GDS is an orchestration layer over real open-source quantum EDA tools. Every backend is cloned, importable, or binary-discovered — not a toy simulator.

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
**`binary found`** = executable at `.tools/`; activate with one API call.
**`skipped`** = adapter returned `status="skipped"` with an explicit reason — no fake data.

---

## ✅ Truthfulness contract

- `executed` — a real solver ran and produced an output file.
- `installed` — the dependency is importable or the binary exists; it did not necessarily run.
- `binary_found` — an executable was detected; not solver evidence.
- `input_files_prepared` — handoff files exist; not solver evidence.
- `skipped` — the solver was unavailable or intentionally not run.
- `planned` — future integration only.

Signoff labels are constrained:

- Level 5 or higher is required for **physics signoff**.
- Level 6 is required for **measurement-calibrated**.
- Skipped solvers, analytical estimates, and generated plots do not count as solver execution.

---

## 🧠 How it works

### Layout backends — priority order

| Priority | Backend | When used |
|---|---|---|
| 1 | **KQCircuits** | Superconducting PCells with full process stack |
| 2 | **Qiskit Metal** | Transmon / qubit resonator geometries |
| 3 | **gdsfactory** | General parametric cells, routing, boolean ops |
| 4 | **local_pcells** | Tests and demos only — never for production/tapeout |

`compile_layout` returns `status="unsupported"` if no backend can handle the request. No fake layout is generated.

### Simulation backends — pick by physics question

| Analysis | Backend | Role |
|---|---|---|
| RF S-parameters / Z0 | **openEMS** (FDTD) | CPW characteristic impedance, S11/S21 |
| Eigenmode f0 / Q | **Palace** (3D FEM) | Cavity resonator modes |
| Capacitance / inductance | **Elmer / FastCap / FastHenry** | IDC coupling, qubit C matrix |
| Nonlinear JPA / JTWPA gain | **JosephsonCircuits.jl** | Pump sweep, gain vs frequency |
| Qubit Hamiltonian / spectrum | **scqubits** | f01, anharmonicity, energy levels |
| SFQ circuit timing | **JoSIM / ngspice** | Josephson voltage pulse propagation |
| Energy participation ratios | **pyEPR** | EPR from eigenmode field solution |

### Provenance labels

Every lineage entry in an extraction result carries a `method_label`:

| Label | Meaning |
|---|---|
| `extracted` | Measured from GDS geometry (e.g. junction overlap area) |
| `estimated` | Analytical formula (e.g. `Lj = Phi0 / (2*pi*Ic)`) — sanity check only |
| `simulated` | Produced by a real solver output file |
| `measured` | Imported from experiment data |

No value may appear in a report without a lineage entry. `source = "LLM"` is invalid and causes immediate failure.

### Five-agent review committee

Score = **minimum** across all five agents — one critical failure cannot be averaged away.

| Agent | Checks |
|---|---|
| **Physics** | Topology, JJ connectivity, CPW ground-gap, impedance vs extracted L and C |
| **Microwave** | Port existence, S-parameter reciprocity/passivity, `.s2p` file present |
| **Fabrication** | DRC min-width/spacing, layer map, JJ overlap, via enclosure |
| **Measurement** | RF port, DC bias, flux line, pump port, wirebond/probe pads |
| **Literature** | Parameter plausibility vs known device classes |

Pass threshold: `final_score >= 90`. The auto-repair loop iterates generate -> review -> fix until accepted or the budget is spent.

### Hard stops (immediate failure, no repair loop)

- Solver panel says `SOLVER NOT EXECUTED` while the report claims simulation.
- Layout generated by the local fallback when a professional backend is available.
- CPW has no valid ground-signal-ground structure.
- JPA has no valid nonlinear pump model.
- Report hides skipped solvers.
- Any claimed value has no provenance.

---

## 🛠 Installation

**Verified local development path** (Python 3.11+):

```bash
git clone https://github.com/JungluChen/Text-to-Layout.git
cd Text-to-Layout
uv sync
uv run pytest
uv run python examples/demo_A_physics_gate.py
```

Installed workflow commands:

```bash
uv run text-to-gds                          # MCP stdio server
uv run text-to-gds-simulation --check
uv run text-to-gds-circuit-design --check
uv run text-to-gds-layout-design --check
uv run text-to-gds-signoff --check
uv run text-to-gds-physics-signoff --check
```

**Skills CLI:**

```bash
npx skills install JungluChen/Text-to-Layout
```

**Check and set up external solver toolchains:**

```powershell
uv run python scripts/check_external_tools.py        # what is available on this machine
uv run python scripts/bootstrap_external_repos.py --clone   # clone optional backend repos
uv run python scripts/setup_external_tools.py        # install Python packages + JosephsonCircuits.jl
```

Julia 1.12.6, JoSIM 2.7, and openEMS 0.0.36 are auto-discovered from `.tools/` — no PATH configuration needed. See [`EXTERNAL_BACKEND_INTEGRATION_STATUS.md`](EXTERNAL_BACKEND_INTEGRATION_STATUS.md) for Palace and Elmer.

---

## 🎯 Skills

| Skill | Role | Source |
|---|---|---|
| **Text-to-GDS** | Core layout generation with PCells, DRC, and JJ simulation | [skills/text-to-gds](skills/text-to-gds/SKILL.md) |
| **Simulation** | JosephsonCircuits.jl, JoSIM, ngspice, scqubits handoffs | [skills/text-to-gds-simulation](skills/text-to-gds-simulation/SKILL.md) |
| **Circuit Design** | Pre-layout circuit target planning (JPA / CPW / qubit) | [skills/text-to-gds-circuit-design](skills/text-to-gds-circuit-design/SKILL.md) |
| **Layout Design** | Compile -> route -> DRC -> extract -> review | [skills/text-to-gds-layout-design](skills/text-to-gds-layout-design/SKILL.md) |
| **Signoff** | Artifact audit, DRC status, simulation check, release validation | [skills/text-to-gds-signoff](skills/text-to-gds-signoff/SKILL.md) |
| **Physics Signoff** | Full signoff engineer: rejects any layout that lacks solver evidence | [skills/text-to-gds-physics-signoff](skills/text-to-gds-physics-signoff/SKILL.md) |

---

## 📐 Validity boundaries

This tool produces a **fabrication-real research prototype**, not a tapeout-ready design.

| What Text-to-GDS provides | What it does NOT provide |
|---|---|
| Boolean-subtracted ground planes, multi-layer JJ geometry | Foundry-calibrated PDK with measured Jc, film thickness |
| Conformal-mapping CPW impedance (analytical cross-check) | EM-converged S-parameters (requires solver execution) |
| Provenance on every derived value | Measurement-calibrated process corners |
| DRC for minimum width/spacing/enclosure | Full foundry DRC deck (antenna, density, metal fill) |
| Junction area from boolean M1 ∩ M2 overlap | Measured Ic from a cryogenic probe station |
| Deterministic review committee with hard failure | Human expert review for tapeout signoff |

**To move from research prototype to tapeout:**

1. Replace generic process parameters with foundry-measured film data.
2. Run an EM solver to convergence (openEMS/Palace/HFSS) and verify against the analytical model.
3. Fabricate test structures and measure Jc, via resistance, CPW loss.
4. Feed measurement data back via `record_experiment_feedback()`.
5. Re-run the review committee with measurement evidence for signoff level >= 5.

Bundled PDK and process values are demonstration data. Every reported value must carry `{value, unit, source, method, confidence}`.

---

## 🤝 Contributing

Issues, PRs, PCell contributions, process-deck adapters, and solver adapters welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md).

## License

MIT. See [LICENSE](LICENSE).
