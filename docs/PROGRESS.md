# Upgrade Progress Log

Living log for the trust-hardening sprint (branch `mvp2-trust-hardening`, merged to `main` 2026-07-02).
Each phase lists: what changed, why, what was verified, what's still open.

## Checklist

- [x] Phase 0 — Baseline & setup
- [x] Phase 1 — Whole-project audit (docs/AUDIT_REPORT.md)
- [x] Phase 2 — Trustworthy evidence model (`textlayout/evidence.py`)
- [x] Phase 3 — Text entry point (`textlayout prompt`, `POST /layout/from-text`)
- [x] Phase 4 — Closed-loop IDC optimization (`textlayout/optimization/idc.py`)
- [x] Phase 5 — Correct simulation flow (FasterCap evidence mapping)
- [x] Phase 6 — Geometry & verification regression coverage
- [x] Phase 7 — Generator consistency matrix (README, validated by Phase 8)
- [x] Phase 8 — Claim-validation CI (`scripts/validate_readme_claims.py`)
- [x] Phase 9 — Testing requirements (all 8 categories)
- [x] Phase 10 — README improvement (30-second demo + support matrix)
- [x] Phase 11 — Final acceptance

## Log

### 2026-07-02 — Phase 0 + 1 (commit `df04e71`)

- Measured baseline: ruff clean, **726 passed / 8 skipped**, `uv build` OK. Suite GREEN.
- Branch review: `review-fixes` and `codex/evidence-first-layout-plugin` were fully
  merged into `main` (`git rev-list --count` = ahead 0); deleted locally and on origin.
- Removed stale never-committed bytecode from `src/textlayout/__pycache__`.

### 2026-07-02 — Phase 2 (commit `0d5ef33`)

- `src/textlayout/evidence.py`: `EvidenceStatus` (ANALYTICAL_ONLY,
  SIMULATION_INPUT_PREPARED, SIMULATION_EXECUTED, PHYSICS_VERIFIED, FAILED,
  SKIPPED_SOLVER_ABSENT) + `QuantityEvidence` pydantic model. A pydantic
  validator makes false claims *unconstructible*: PHYSICS_VERIFIED requires a
  named solver + parser, an existing non-empty solver-owned output file, and
  error ≤ tolerance; ANALYTICAL_ONLY cannot name a solver; skipped/prepared
  cannot carry extracted values. `compare_extracted_to_target()` computes the
  status — callers can never pass it in.
- Verified: `tests/textlayout_suite/test_evidence_contract.py` (8 tests) proves
  each rule, including the missing/empty-output-file rejections.

### 2026-07-02 — Phases 3 + 4 + 5 (commit `a4a5669`)

- Phase 3: `prompt.py` deterministic regex parser (no LLM/API key) →
  `DesignIntent`; raises `PromptParseError` on ambiguity (empty prompt, unknown
  component, unknown substrate, multi-component requests, bare IDC with no
  information). CLI subcommand `textlayout prompt` and API
  `POST /layout/from-text` (HTTP 400 on parse errors). All three brief example
  prompts parse under unit test; four malformed prompts fail loudly.
- Phase 4: `optimization/idc.py` closed loop — coarse `finger_pairs`, fine
  `overlap_um` (capacitance linear in overlap); width/gap honoured as
  constraints, never tuned below process minimums; user-supplied values are
  fixed, not overridden. Converges on 0.2/0.6/1.5 pF under test; impossible
  constraints return `converged=False` with an explanatory note.
- Phase 5: `simulation/evidence_map.py` — single conservative mapping from
  `SimulationResult` to `QuantityEvidence` (`input_files_prepared` →
  SIMULATION_INPUT_PREPARED, `skipped` → SKIPPED_SOLVER_ABSENT, `failed` →
  FAILED, `executed` → tolerance comparison; unknown statuses demote to FAILED).
  Empty stderr logs are excluded from claimed solver outputs.
- `workflows/from_text.py` orchestrates the full closed loop and writes the
  eight contract files: intent.json, layout.json, output.gds, output.svg,
  verification.json, simulation.json, optimization.json, report.md.
- Verified: solver-absent path (SKIPPED_SOLVER_ABSENT, no extracted value, no
  PHYSICS_VERIFIED anywhere in the report) and solver-present path via a real
  fake-solver subprocess (PHYSICS_VERIFIED at 0.33% error; SIMULATION_EXECUTED
  at 25% error). mypy strict clean (65 files), ruff clean, 759 passed.

### 2026-07-02 — Phase 6

- Already covered by `tests/textlayout_suite/test_verification.py`
  (`test_gap_below_min_fails`, `test_width_below_min`, `test_unknown_layer_fails`,
  rules-override failure) — deliberately invalid geometry fails verification,
  and `GenerateWorkflow` never exports failing geometry. No new code needed;
  gap analysis recorded in AUDIT_REPORT.md.

### 2026-07-02 — Phases 7 + 8 + 10 (commit `cd05dbd`)

- README: new `## 30-second demo` (exact demo command + generated-files list +
  honest solver-absent result table + limitation statement) and
  `## Component support matrix` (IDC full closed loop; CPW/Spiral/Resonator
  geometry+analytical; SQUID experimental).
- `scripts/validate_readme_claims.py`: parses the support matrix; every
  Geometry/Analytical/Solver-input "yes" must map to committed files; a
  "Solver executed"/"Physics verified" **yes** requires committed solver-owned
  output artifacts (and a PHYSICS_VERIFIED evidence record); benchmark-table
  execution claims require artifacts in the linked folder; the demo command
  must exist in the CLI; the limitation sentence is mandatory.
- CI (`.github/workflows/ci.yml`) runs the validator before ruff/pytest/build.
- Guardrail proof (Phase 8 DoD): `test_readme_claims.py` injects three false
  claims into a doctored README copy and asserts the validator fails each —
  the permanent equivalent of the scratch-branch experiment.

### 2026-07-02 — Phase 9 (test coverage by category)

1. Prompt parsing — `test_prompt_parsing.py` (9 tests)
2. IDC optimization — `test_idc_optimization.py` (8 tests)
3. CLI integration — `test_from_text_workflow.py::test_cli_prompt_produces_all_required_files`
4. API integration — `test_api_from_text.py` (2 tests)
5. Solver-absent — `test_from_text_workflow.py::test_solver_absent_is_never_physics_verified`
   (+ existing `test_open_source_simulation.py`)
6. Solver-present — `test_from_text_workflow.py::test_solver_present_*` (real
   subprocess fake solver; verified vs executed-not-verified)
7. Golden IDC benchmark — `test_from_text_workflow.py::test_golden_idc_benchmark_is_stable_and_honest`
8. README claims — `test_readme_claims.py` (4 tests)

### 2026-07-02 — Phase 11 final acceptance (all measured)

| Gate | Result |
| - | - |
| `uv run python scripts/validate_readme_claims.py` | PASS |
| `uv run ruff check .` | PASS |
| `uv run pytest` | **763 passed, 8 skipped** |
| `uv build` | PASS |
| `uv run mypy` (strict, src/textlayout) | PASS (65 files) |
| Demo command → 8 contract files | PASS (exit 0; all files non-empty) |

Demo report states explicitly: geometry verification PASS, simulation status
`SKIPPED_SOLVER_ABSENT` ("solver not installed; no physics verification was
performed"), optimizer converged at 0.0% analytical error, and the
not-fabrication-ready limitation.

## Consolidation & Restructure (2026-07-02, post-sprint)

Rollback point: tag `pre-consolidation-2026-07-02` (= efba53b, pushed).
Full merge audit trail: [BRANCH_INVENTORY.md](BRANCH_INVENTORY.md).

### Branches merged

- No named branches carried unmerged commits (`git cherry` + ancestry checks on
  the recorded tips of the three branches deleted earlier on 2026-07-02
  retroactively confirmed nothing was lost).
- **One real unmerged item found:** `stash@{0}` "epitaxy: pre-switch from
  mvp2-trust-hardening" (90 files, +3416/−943 vs its parent a87f6b8) — the
  uncommitted MVP2 working tree. Materialized as branch `recovered/mvp2-stash`
  (commit 63ae636), merged into main as **e0f4ad3**, branch + stash deleted
  only after the merged tree passed the full gate.

### Conflicts resolved (each side stated, none silent)

- 9 add/add and content conflicts (`prompt.py`, `optimization/*`,
  `workflows/from_text.py`, `workflows/__init__.py`, backend files, README,
  `test_readme_claims.py`) resolved **toward main's committed rebuilds**; the
  stash held older drafts of the same features (see BRANCH_INVENTORY §1).
- `cli.py`/`errors.py` auto-merged BOTH implementations (duplicate
  `_cmd_prompt`, broken import, orphaned `compile` subcommand,
  `PromptCompilationError`); cleaned to main's implementation by hand.
- Stash README rework discarded; its intent (linked trust artifacts, explicit
  not-public-plugin disclaimer) preserved via the new README
  "Trust and reproducibility" section; `test_product_docs.py` table-split
  assertion adapted to the consolidated single benchmark table + support matrix.
- **Policy reversal:** `examples/**/.generation_meta.json` untracked and
  gitignored (stash intent wins — they hold real wall-clock timestamps;
  committed provenance is the normalized block in output/verification.json).

### Structure changes (Phase D, one line each)

- `docs/ARCHITECTURE.md` created: one-minute map + dependency rule + "How to
  add a new generator" walkthrough mapped to support levels A/B/C.
- Root `ARCHITECTURE.md` scoped with a legacy banner pointing to the new doc.
- `src/text_to_gds/__init__.py` carries an explicit FROZEN LEGACY notice;
  package intentionally NOT moved to `legacy/` — the import path is
  load-bearing for the MCP server, 5 console scripts, and ~60 test modules
  (reason recorded in docs/ARCHITECTURE.md §Legacy).
- Duplicate target-comparison logic consolidated: shared
  `simulation/models.py::target_comparison()` now used by both `runners.py`
  and `fastercap.py` (was: two hand-rolled copies of the same dict).
- Dead drafts removed in the merge: `evidence_contract.py`,
  `check_readme_claims.py`, draft prompt/optimization/from_text modules and
  their tests (zero remaining references verified by grep).
- CI `quality-gates` job (from the stash) wired to `validate_readme_claims.py`
  (the canonical validator) instead of the deleted `check_readme_claims.py`.

### Incident note

`Text-to-GDS_Academic_Industrial_Validation_Roadmap.md` and `TopTask.md`
disappeared from the working tree between merge `e0f4ad3` and `84b7bdb`
(cause unidentified — no repo script touches them) and were accidentally
committed as deletions by a bulk `git add -A`. Restored in `803c494`; any
intentional removal should be its own reviewed commit.

### Test count

| Point | Result |
| - | - |
| Before consolidation (baseline) | 763 passed, 8 skipped |
| After merge + consistency fixes | **794 passed, 8 skipped** (+31 from recovered tests) |

## Still open (honest backlog)

- CPW/Spiral/Resonator closed-loop tuning (only IDC has the full loop).
- No committed solver-executed benchmark artifact (requires FasterCap in CI or
  a locally-run benchmark commit); the support matrix truthfully says
  "environment-dependent".
- Legacy `src/text_to_gds` package remains frozen (documented decision, see
  AUDIT_REPORT.md §Package architecture); full retirement is future work.
