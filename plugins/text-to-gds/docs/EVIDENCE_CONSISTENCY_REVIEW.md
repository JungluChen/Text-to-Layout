# Evidence consistency review

Generated from committed artifacts (`examples/showcase/*/simulation.json`,
`index.json`, `report.md`, `tile_simulation_map.json`), not from README prose.
Every number below is quoted from the artifact that owns it; re-derive it with
`uv run python scripts/generate_showcase_examples.py --force` if you doubt it.

## Incident: stale SKIPPED_SOLVER_ABSENT claims (fixed 2026-07-05)

Before this review, `examples/showcase/index.json` and the root `README.md`
claimed `SKIPPED_SOLVER_ABSENT` for examples 2 (CPW) and 5 (resonator) — "no
EM solver was executed." That was false: the committed `simulation.json` for
both already showed `solver_executed=true` with a real openEMS run (WSL
Octave driver, committed Touchstone `.s2p`, stdout/stderr, timestamps). The
openEMS/CSXCAD/Octave/scikit-rf stack is present in this environment
(`textlayout doctor --strict-em` passes); the two examples had been executed
in a prior session, but `index.json` and the per-example `README.md` — both
*generated* artifacts, not hand-written — were never regenerated afterward,
so they still described the pre-execution state.

A second bug compounded this: the per-example "Limitation" text was a
hardcoded string per component (e.g. "no EM solver was executed") baked into
`scripts/generate_showcase_examples.py` at module load time, independent of
whether the solver actually ran. Even after regenerating, examples 2 and 5
would have kept claiming "no EM solver was executed" directly under a
"Solver executed: **yes**" line. Fixed by computing the limitation text from
the actual `simulation.json` outcome (`_limitation_text()` in
`scripts/generate_showcase_examples.py`), separating the *execution-status*
clause from the *always-true physics caveat* for each component.

Both bugs are now also caught mechanically: `scripts/validate_readme_claims.py`
gained `_check_index_matches_simulation()` and `_check_report_matches_simulation()`,
which fail the build if `index.json` or `report.md` ever again disagrees with
the example's own `simulation.json` — in either direction (overclaim or
stale-negative).

## Per-example ground truth (post-regeneration, 2026-07-05)

### 1. `01_idc_0p6pf` — 0.6 pF IDC

- Target: 0.6 pF mutual capacitance
- Solver: FasterCap — **executed: true**
- Extracted: 0.598641 pF vs target 0.6 pF — error **-0.226%** (tolerance 5%)
- Within tolerance: **true**
- Evidence status: **PHYSICS_VERIFIED**
- Fabrication status: **NOT_FABRICATION_READY**
- Not modeled: self-resonance, loss, finite metal thickness; effective-medium
  electrostatic model only.

### 2. `02_cpw_50ohm` — 50 ohm CPW feedline

- Target: 50.0 ohm characteristic impedance
- Solver: openEMS+scikit-rf — **executed: true** (WSL Octave driver, real FDTD run)
- Extracted: 30.917129182835225 ohm vs target 50.0 ohm — error **-38.166%** (tolerance 5%)
- Within tolerance: **false**
- Evidence status: **SIMULATION_EXECUTED** (not PHYSICS_VERIFIED — executed but outside tolerance; not SKIPPED — the solver ran)
- Fabrication status: **NOT_FABRICATION_READY**
- Not modeled: loss, dispersion, connector transitions. The large error suggests
  the geometry-to-target mapping (or port/mesh setup) needs revisiting before
  this can be retuned toward 50 ohm — not yet investigated in this pass.

### 3. `03_idc_cpw_test_structure` — IDC + CPW test structure

- Target: 0.6 pF mutual capacitance (embedded IDC region only)
- Solver: FasterCap — **executed: true**, on the embedded IDC extraction region only
- Extracted: 0.610019 pF vs target 0.6 pF — error **1.670%** (tolerance 5%)
- Within tolerance: **true**
- Evidence status: **PHYSICS_VERIFIED for the embedded IDC region only**
- Fabrication status: **NOT_FABRICATION_READY**
- Not modeled: CPW launches, feed transitions, and the whole assembled
  structure are not full-wave verified. `region_evidence_map.json` records a
  separate CPW-launch-and-feed openEMS run (`SIMULATION_EXECUTED`,
  10% region tolerance) that is not part of the PHYSICS_VERIFIED claim.

### 4. `04_spiral_inductor_3nh` — 3 nH spiral inductor

- Target: 3.0 nH
- Solver: FastHenry — **executed: true**, after two geometry iterations (`optimization.json`)
  - Iteration 1: 2.751263754746667 nH — error -8.291% (outside tolerance)
  - Iteration 2 (accepted): 2.9583084202149137 nH — error **-1.390%** (within tolerance)
- Within tolerance: **true**
- Evidence status: **PHYSICS_VERIFIED**
- Fabrication status: **NOT_FABRICATION_READY**
- Wording check: no capacitance/pF language found describing the target
  quantity. Generic shared-schema `capacitance_*` fields in `simulation.json`
  are correctly `null` / `"NOT_APPLICABLE"` for this inductance example.
- Not modeled: conductivity and metal thickness are generic process
  assumptions, not a foundry PDK value.

### 5. `05_quarter_wave_resonator_6ghz` — 6 GHz quarter-wave resonator

- Target: 6.0 GHz resonance frequency
- Solver: openEMS+scikit-rf — **executed: true** (WSL Octave driver, real FDTD run)
- Extracted: 3.0 GHz vs target 6.0 GHz — error **-50.0%** (tolerance 5%)
- Within tolerance: **false**
- Evidence status: **SIMULATION_EXECUTED** (not PHYSICS_VERIFIED; not SKIPPED)
- Fabrication status: **NOT_FABRICATION_READY**
- Not modeled: the extracted resonance is exactly half the target, consistent
  with a λ/4-vs-λ/2 mode or boundary-condition mismatch between the
  analytical length model and the FDTD setup — not root-caused in this pass.
  Boundary placement and mesh convergence have not been reviewed.
- Documentation note (not a bug): `extraction/capacitance_input/simulation_manifest.json`
  is a **pre-run input-preparation snapshot** (`solver_executed: false`,
  `status: "input_files_prepared"`) written before the solver runs. It will
  always show pre-run state even after a successful execution — the
  post-run outcome lives in the sibling `simulation.json`, not the manifest.
  This is by design (the manifest records what was *prepared*, not what
  happened), but it looks like a contradiction at a glance; treat
  `simulation.json` as authoritative for execution status.

### 6. `06_research_test_chip` — 2mm x 2mm research test chip

- Full tile: **not modeled**. `full_tile_solver_executed: false`,
  `full_tile_status: NOT_MODELED`. A Gmsh + Palace full-tile path is prepared
  (`full_tile_palace/full_tile.geo`, `palace.json`, `full_tile.msh`) but not
  executed because Palace is not installed in this environment
  (`textlayout doctor --strict-fullchip` reports it missing).
- Sub-block evidence (`tile_simulation_map.json`, rendered in
  `tile_evidence_dashboard.json` / `subblock_evidence.md`):
  - IDC: FasterCap executed; 0.6973109999999999 pF vs 0.6 pF target — error
    16.218%, outside tolerance. `SIMULATION_EXECUTED`.
  - CPW: openEMS executed; 38.47287247108259 ohm vs 50.0 ohm target — error
    -23.054%, outside tolerance. `SIMULATION_EXECUTED`.
  - SpiralInductor: FastHenry executed; 2.751263754746667 nH extracted; no
    tile-prompt target to compare against. `SIMULATION_EXECUTED`.
  - Resonator: openEMS executed (nominal reference sub-block, not embedded in
    tile geometry); 3.0 GHz vs 6.0 GHz target — error -50.0%, outside
    tolerance. `SIMULATION_EXECUTED`.
  - AlignmentMarksAndLabels: geometry-only, no solver model applies.
- Evidence status: **ANALYTICAL_ONLY for the full tile**; sub-block map has
  real solver executions but none within tolerance and no full-tile solve.
- Fabrication status: **NOT_FABRICATION_READY**
- Not modeled: inter-block coupling, package, wirebond, connector
  transitions, and whole-tile modes. Sub-block geometry is parameter-identical
  to the corresponding standalone example but simulated in isolation, not as
  assembled in the tile.

## Known remaining artifact-quality issue

`tile_simulation_map.json`'s Resonator sub-block contains a literal `NaN`
JSON token (`"s21_magnitude_at_resonance": NaN`), emitted by
`extract_resonance_metrics_from_touchstone()` in
`src/textlayout/simulation/runners.py` when the resonance-frequency Touchstone
data does not have a well-defined |S21| at the extracted index. Python's
`json` module accepts this, but it is not valid per the JSON spec (RFC 8259)
and will break strict parsers (e.g. `JSON.parse` in JavaScript). Not fixed in
this pass — flagged as a follow-up; the underlying value should serialize as
`null` when undefined rather than `NaN`.

## Absolute local path scan

A repo-wide scan for `C:\Users`, `/mnt/c/Users`, `/home/`, and
`/tmp/fastercap_work` in `README.md`, `docs/`, `examples/`, `src/`, `scripts/`
found no matches in committed project files (only in vendored `.tools/`
third-party sources, which are git-ignored and out of scope). This is also
enforced going forward by `_check_no_committed_absolute_paths()` and
`_check_showcase_paths()` in `scripts/validate_readme_claims.py`.
