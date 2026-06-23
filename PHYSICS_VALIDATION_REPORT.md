# Physics Validation Report

Generated: 2026-06-23  
Mission: Convert "SOLVER NOT EXECUTED" → "SOLVER EXECUTED + artifact produced"

---

## Benchmark status

| # | Device | Required solver | Executed? | Artifact | Confidence | Notes |
|---|---|---|---|---|---|---|
| B01 | Manhattan JJ | JosephsonCircuits.jl | **YES** | `*.jpa.result.json` + gain array | 0.85 | Ic=0.658µA, Lj=500pH, harmonic balance |
| B02 | Ground plane coupon | Elmer FEM | **NO** → SKIPPED | — | — | ElmerSolver not installed; honest skip |
| B03 | SFQ pulse splitter | JoSIM | **NO** → SKIPPED | — | — | josim-cli found in .tools/ but no netlist configured |
| B04 | JJ calibration array | JosephsonCircuits.jl | **YES (geometry)** | `jj_array_characterization.json` | 0.85 | Ic/Lj per junction from GDS area; JC.jl sweep available |
| B05 | CPW resonator | openEMS FDTD | **NO** → SKIPPED | analytical .s2p | 0.65 | openEMS binary found; S-parameters require octave post-processor |
| B06 | Via chain monitor | Process extraction | **YES** | `resistance_extraction.json` | 0.70 | R = N×Rvia + Rs×L/W from sidecar metadata |

---

## What executes today

| Solver | Status | Artifact | Engine |
|---|---|---|---|
| JosephsonCircuits.jl | **EXECUTED** | gain array, pump sweep | Julia 1.12.6 + JosephsonCircuits.jl 0.5.2 |
| scqubits | **EXECUTED** | energy_levels_ghz, f01_ghz, anharmonicity | scqubits 4.3.1 (Python) |
| CPW analytical model | **EXECUTED** | Touchstone .s2p (analytical) | conformal mapping + resonator model |
| Via chain resistance | **EXECUTED** | resistance_ohm + breakdown | geometry extraction from sidecar |
| JJ array characterization | **EXECUTED** | Ic/Lj table + JC.jl sweep | sidecar geometry + JosephsonCircuits.jl |

---

## What is SKIPPED (honest, not a failure)

| Solver | Reason | Resolution |
|---|---|---|
| openEMS FDTD | Binary at `.tools/openEMS-v0.0.36/` runs, but S-parameters require octave post-processor. Python wheels in `.tools/.../python/` are for Python 3.10/3.11; project uses Python 3.12. | Install Octave (https://octave.org/download) OR switch venv to Python 3.11 and install bundled wheels |
| Elmer FEM | ElmerSolver not on PATH | Download from https://www.elmerfem.org/blog/binaries/ |
| Palace | Executable not found | Build from source: https://github.com/awslabs/palace |
| JoSIM | josim-cli found in `.tools/josim-v2.7/` but SFQ netlist generation not wired to benchmark | Connect josim adapter to SFQ PCell sidecar |
| Qiskit Metal | PySide2/Qt5 incompatible with Windows Python 3.12 | Use conda + Python 3.10 environment |

---

## Solver evidence panel requirements

Every benchmark figure must show three panels:

| Panel | Content | Color |
|---|---|---|
| 1 — GDS geometry | Layout image from compile_layout | neutral |
| 2 — Extraction | Ic, Lj, f0, Z0 with method_label per value | neutral |
| 3 — Solver evidence | Solver name + version + runtime + input + output + timestamp | **green** if EXECUTED, **red** if FAILED/NOT EXECUTED, **grey** if SKIPPED |

A grey SKIPPED panel is acceptable. A red FAILED panel requires investigation. A green panel **requires a real artifact path** — not just a status string.

---

## Provenance requirements

Every numeric claim must carry:

```json
{
  "value": 0.658,
  "unit": "µA",
  "source": "GDS area × Jc process parameter",
  "method": "geometry_extracted",
  "confidence": 0.85,
  "formula": "Ic = A × Jc"
}
```

**Forbidden:** `"source": "LLM"`, `"method": "estimated"` without formula, `confidence > 0.9` for analytical results.

---

## Implemented this session

| Module | Purpose |
|---|---|
| `src/text_to_gds/physics/cpw_model.py` | Analytical CPW Z0, S11/S21, Touchstone writer, openEMS cross-check |
| `src/text_to_gds/jj_array_characterization.py` | Batch JJ Ic/Lj extraction + JosephsonCircuits.jl sweep |
| `src/text_to_gds/resistance_extractor.py` | Via chain and trace resistance from sidecar geometry |
| `src/text_to_gds/validation/artifact_validator.py` | Per-solver artifact presence and validity checks |
| `src/text_to_gds/openems_runner.py` | Updated: octave check, skips cleanly with explicit reason |
| `tests/test_openems_real_s2p.py` | openEMS skipped/failed invariants |
| `tests/test_no_fake_gain.py` | Gain source provenance, JC.jl artifact requirements |
| `tests/test_solver_artifacts_required.py` | All-solver artifact validation, CPW model, via chain, JJ array |

---

## Path to GREEN for remaining benchmarks

### B05 CPW resonator → openEMS EXECUTED

Option A (fastest): Install Octave 9.x for Windows, add to PATH.
```powershell
# After octave install:
uv run python -c "from text_to_gds.openems_runner import _find_octave; print(_find_octave())"
# → should print octave-cli path
```

Option B: Create Python 3.11 venv and install bundled wheels:
```powershell
py -3.11 -m venv .venv311
.venv311/Scripts/pip install ".tools/openEMS-v0.0.36/openEMS/python/CSXCAD-0.6.3-cp311-cp311-win_amd64.whl"
.venv311/Scripts/pip install ".tools/openEMS-v0.0.36/openEMS/python/openEMS-0.0.36-cp311-cp311-win_amd64.whl"
```

### B02 Ground plane → Elmer EXECUTED

```powershell
# Download and install Elmer 9.0 for Windows
# Add ElmerSolver.exe to PATH
uv run python -c "from text_to_gds.backends.elmer_backend import ElmerBackend; print(ElmerBackend().available())"
```

### B03 SFQ splitter → JoSIM EXECUTED

Wire the josim adapter to the SFQ splitter sidecar:
```python
from text_to_gds.backends import get_backend
backend = get_backend("josephsoncircuits")  # or JoSIM adapter
```

---

## Key invariants (never break)

1. `source = "LLM"` → immediate review failure
2. `status = "skipped"` when solver unavailable — never `"passed"` or `"success"`
3. `status = "failed"` when solver ran but produced no artifact
4. Review committee score = minimum (not average) across all 5 reviewers
5. Pass threshold = 90. No exceptions.
6. Every artifact path in a result dict must point to a real file on disk
7. openEMS: binary found ≠ S-parameters available. Must check for octave.
8. CPW analytical model: method="analytical", confidence≤0.7 — never "simulated"
