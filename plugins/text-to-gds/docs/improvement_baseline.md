# Improvement baseline

Reproducible record of the repository state at the start of the trustworthiness
upgrade. Every number here was produced by running the command shown, on the
machine described, at the commit named. Nothing is copied from another status
document.

## Environment

| Fact | Value |
| --- | --- |
| Baseline commit | `358c983d` ("evidence(showcase): 02_cpw_50ohm is PHYSICS_VERIFIED after the substrate fix") |
| Branch | `main` |
| Python | 3.12.10 (CPython, MSC v.1943, 64-bit) |
| Package manager | `uv` |
| OS | Windows 11 Home 10.0.26200 |
| Declared support | `requires-python = ">=3.11"`; CI matrix 3.11 / 3.12 on ubuntu + windows |

Reproduce:

```bash
git checkout 358c983d
uv sync --dev
uv run python -c "import sys; print(sys.version)"
```

## Working-tree state as found

The repository was **not clean** when this work started. Five files were
modified and five were untracked — an in-progress measurement-calibration
overlay feature.

```
 M src/textlayout/cli.py
 M src/textlayout/measurement/{__init__,models,report}.py
 M .gitignore                      (line-ending-only diff)
?? src/textlayout/measurement/{loaders,overlay}.py
?? examples/measurement_fixtures/{measurements_synthetic.csv,measurements_synthetic.json,predictions_synthetic.json}
```

That work was **broken**: it did not lint and it failed two tests. It was
completed rather than discarded (commit `ab001d42`).

## Measured gate results

Each row is a command actually executed. "Baseline" is clean `358c983d`;
"As found" is `358c983d` plus the uncommitted working tree.

| Gate | Command | Baseline `358c983d` | As found (dirty tree) |
| --- | --- | --- | --- |
| Tests | `uv run pytest` | **1165 passed, 6 skipped** | 1163 passed, **2 failed**, 6 skipped |
| Lint | `uv run ruff check .` | **passed** | **1 error** (`F821` undefined `CalibrationOverlay`) |
| Types | `uv run mypy` | **3 errors, 2 files** | **7 errors, 3 files** |
| README claims | `uv run python scripts/validate_readme_claims.py` | passed | passed |
| Benchmarks | `uv run python scripts/check_benchmarks.py --strict` | passed | passed |
| Build | `uv build` | not run at baseline | — |

### The two failing tests (as found)

```
tests/textlayout_suite/test_measurement.py::TestReportsAndCLI::test_cli_measurement_calibrate
tests/textlayout_suite/test_measurement.py::TestReportsAndCLI::test_cli_measurement_calibrate_production_flag
```

### Type errors at clean baseline

`[tool.mypy]` declares `strict = true` over `src/textlayout`, but **mypy is not
run by any GitHub Actions workflow** — so these 3 errors were never gating:

```
src/textlayout/simulation/sparameters.py:31  unused/mismatched type: ignore  (x2)
src/textlayout/yield_model/monte_carlo.py:75  Missing type arguments for generic type "ndarray"
```

This is a live gap: `ci.yml` runs `validate_readme_claims`, `ruff`, `pytest`,
`uv build`. `test.yml` runs `pytest` + `ruff`. Neither runs `mypy`.

## Skipped tests (6) and why

All six skip honestly — none is a silent pass.

| Test | Reason |
| --- | --- |
| `test_physics_engine.py:688` | `scqubits` not installed |
| `test_research_execution.py:39` | `scqubits` not installed |
| `test_research_execution.py:59` | `qcodes` not installed |
| `test_research_execution.py:78` | `optuna` not installed |
| `test_research_execution.py:162` | needs `TEXT_TO_GDS_RUN_EXTERNAL=1` (FDTD/Julia) |
| `test_research_execution.py:182` | needs `TEXT_TO_GDS_RUN_EXTERNAL=1` (FDTD/Julia) |

## Solver availability on this machine

From `uv run textlayout doctor --json`. This matters because most CI runners
have *none* of these — results that depend on them must skip honestly there.

| Section | Tool | Status |
| --- | --- | --- |
| Core | Python, textlayout, gdsfactory, klayout.db, langgraph | ok |
| Extraction | FasterCap / FastCap | **ok** |
| Extraction | FastHenry / FastHenry2 | **ok** |
| RF / EM | openEMS, CSXCAD, Octave (+ matlab paths) | **ok** (via WSL) |
| RF / EM | scikit-rf 2.0.1 | ok |
| 3D FEM | Gmsh, meshio | ok |
| 3D FEM | **Palace** | **absent** |
| Circuit | JoSIM | ok |
| Circuit | **WRspice / ngspice** | **absent** |

Not installed as Python packages: `scqubits`, `qcodes`, `optuna`.

## Evidence model at baseline

`src/textlayout/evidence.py` defines `EvidenceStatus` with six states:
`ANALYTICAL_ONLY`, `SIMULATION_INPUT_PREPARED`, `SIMULATION_EXECUTED`,
`PHYSICS_VERIFIED`, `FAILED`, `SKIPPED_SOLVER_ABSENT`.

Structural guards were present and genuinely enforced (solver named, parser
named, output file exists and is non-empty, error within tolerance).

### Defect found at baseline

The tolerance guard was `error_percent > tolerance_percent`. Because
`NaN > x` is `False` for every `x`, a **NaN error was admitted as
`PHYSICS_VERIFIED`**. Reproduced on `358c983d`:

```python
QuantityEvidence(status=EvidenceStatus.PHYSICS_VERIFIED,
                 extracted_value=float("nan"), error_percent=float("nan"), ...)
# -> constructed successfully
# summary_line(): "capacitance: PHYSICS_VERIFIED - openEMS extracted nan pF ..."
```

`compare_extracted_to_target()` had the matching defect: non-finite output was
labelled `SIMULATION_EXECUTED`, asserting a value had been extracted from
garbage. Fixed in `ce0c4a4d`; states `SIMULATION_INVALID` and
`CONVERGENCE_FAILED` added.

## Document currency

The repository carries 20+ top-level status/audit markdown files
(`PROJECT_STATUS.md`, `CURRENT_STATUS.md`, `PHYSICS_VALIDATION_REPORT.md`,
`PROJECT_AUDIT.md`, `REVIEW_REPORT.md`, `TOY_PATH_AUDIT.md`, ...). These are
manually maintained and are **not** generated from evidence, so they can drift
from what the code proves. `scripts/check_benchmarks.py` and
`scripts/validate_readme_claims.py` cover only the README and the benchmark
manifests.

`CLAUDE.md` states solver availability "as of 2026-06-23" that contradicts the
`doctor` output above (it lists openEMS as SKIPPED; openEMS executes here).
Treat generated evidence, not prose, as the source of truth.

## Two CI jobs were already red at baseline

Neither is caused by the work in this branch; both were verified by checking
out `358c983d` and running the job's own commands.

1. **`bundle-sync`.** Regenerating `plugins/text-to-gds` at the baseline commit
   produced **65 changed files / 5452 insertions** — the bundled plugin copy
   had drifted far behind `src/` (`workflows/from_text.py` alone was ~1000
   lines behind). Fixed in `e6553487`.
2. **Benchmark determinism, on any machine that has openEMS.** The generator
   embedded `discover_openems_stack()` output — absolute host paths including
   the local username — into the committed `openems_model.json` and
   `simulation_manifest.json`. On the CI runner openEMS is absent so the block
   was empty and the gate passed; on a solver-equipped machine regenerating
   dirtied the tree. Fixed in `862d67b3`.

The second is why the baseline default-run appeared clean here: the generator
skips benchmarks whose `layout.json` is unchanged, which also masked that the
committed `verification.json` files were missing the `idc_two_net_connectivity`
and `idc_no_comb_shorts` checks the verifier actually runs.

## State after this work

Every row was run at `e6553487`.

| Gate | Baseline `358c983d` | After |
| --- | --- | --- |
| `uv run pytest` | 1165 passed, 6 skipped | **1264 passed, 6 skipped** |
| `uv run ruff check .` | passed | passed |
| `uv run mypy` | **3 errors** (ungated) | **Success, 128 files** (now gated in CI) |
| `uv run uv build` | not run | passed (wheel + sdist) |
| clean-wheel install | `textlayout --version` → **0.2.0** (wrong) | → **0.3.0** |
| `check_benchmarks.py --strict` | passed | passed |
| `validate_readme_claims.py` | passed | passed |
| acceptance freshness | passed | passed |
| benchmark determinism | passed *only without openEMS* | passes **with** openEMS |
| `bundle-sync` | **FAIL** (65 files stale) | passed |
| API smoke | passed | passed |
