# Branch Inventory & Consolidation Audit Trail

Date: 2026-07-02. Rollback point: tag `pre-consolidation-2026-07-02` (= `efba53b`, pushed).
Baseline on `main` before any consolidation: `uv run pytest` → **763 passed, 8 skipped** (exit 0).

## Method

Per the safety rules, merge state was verified with **both** `git log main..<tip>`
/ `git rev-list --count` **and** patch-identity (`git cherry main <tip>`), plus
`git merge-base --is-ancestor <tip> main` for branches whose refs were already
deleted in the prior session (their tip SHAs were recorded at deletion time).
`git fetch --all --prune` was run first; `git stash list` was checked for
stranded work (this found the one real item below).

## Inventory

| Branch / ref | Last commit | Ahead of main | Merged by content? | Summary | Recommended action |
| - | - | - | - | - | - |
| `main` | efba53b 2026-07-02 | — | — | canonical; closed-loop IDC sprint | keep |
| `origin/main` | efba53b | 0 | yes (identical) | remote mirror | keep |
| `review-fixes` (deleted 2026-07-02, tip `4195ae9`, 2026-06-22, JungluChen) | 2026-06-22 | 0 | **yes** — `merge-base --is-ancestor` true, `git cherry` empty | review fixes, long merged | already deleted; retro-verified, nothing lost |
| `codex/evidence-first-layout-plugin` (deleted 2026-07-02, tip `839dcfd`, 2026-06-29, JungluChen) | 2026-06-29 | 0 | **yes** — ancestor of main, `git cherry` empty | evidence-first plugin work, merged via PR flow | already deleted (local + origin); retro-verified, nothing lost |
| `mvp2-trust-hardening` (deleted 2026-07-02, tip `efba53b`) | 2026-07-02 | 0 | **yes** — tip *is* main | this sprint's work branch | already deleted after fast-forward |
| **`stash@{0}` "epitaxy: pre-switch from mvp2-trust-hardening"** (2026-07-02 10:24 +0800, parent `a87f6b8`) | 2026-07-02 | ~1 virtual commit, 90 files, +3416/−943 | **NO — real unmerged work** | uncommitted MVP2 trust-hardening working tree: solver execution runners, acceptance suite, GDS determinism, exact-polygon DRC, CI quality gates, docs | **merge-with-conflict-resolution** (see below) |

No other branches, remotes, or stashes exist. The prior session's deletions are
hereby retroactively confirmed safe by the stronger double-check method.

## The recovered stash — content classification

The stash predates (same day, hours before) the closed-loop sprint now on
`main`, and its parent is `a87f6b8`. Its content splits into:

**(1) Superseded drafts — discard, with reason.** These files were rebuilt from
scratch (committed, tested, mypy-strict) in commits `0d5ef33`/`a4a5669`; the
stash holds older drafts of the same features. Discarding the stash side is an
explicit decision, not an accident:

| Stash file | Superseded by (on main) |
| - | - |
| `src/textlayout/prompt.py` (draft) | `src/textlayout/prompt.py` (committed, 9 tests) |
| `src/textlayout/evidence_contract.py` | `src/textlayout/evidence.py` (structural validator, 8 tests) |
| `src/textlayout/optimization/{__init__,idc}.py` (draft) | same paths on main (committed, 8 tests) |
| `src/textlayout/workflows/from_text.py` (draft: `run_from_text`/`compile_text`) | `FromTextWorkflow` (committed; 8-file contract) |
| `scripts/check_readme_claims.py` | `scripts/validate_readme_claims.py` (in CI) |
| CLI `prompt`/`compile` subcommands + `PromptCompilationError`; backend `/layout/from-text` variant + `CompileText*` models | main's `prompt` subcommand, `PromptParseError`, `/layout/from-text` |
| `tests/…/test_readme_claims.py`, `test_prompt_compiler.py`, `test_prompt_flow.py`, `tests/golden_layouts/expected_idc_prompt.json` | `test_readme_claims.py`, `test_prompt_parsing.py`, `test_from_text_workflow.py` |
| `README.md` rework (split tables) | main's claim-validated README (30-second demo + support matrix); honest-status intent preserved there |

**(2) Real unmerged work — merge.**

- `src/textlayout/simulation/runners.py` — FastHenry execution+parse (Zc.mat → L),
  openEMS Touchstone post-processing via scikit-rf (+fallback parser), graceful
  solver-missing handling.
- `simulation/models.py` — `target_comparison`, derived `evidence_stage`,
  `physics_verified` gate (derived, never stored). `engine.py` — `execute=True`
  routing for spiral/CPW/resonator. `fastercap.py` — optional target comparison.
- `verification/checks.py` — exact polygon-to-polygon clearance (segment
  intersection + containment + point-segment distance) replacing bbox gap.
- `exporters/gds_exporter.py::canonicalize_gds` (KLayout rename + no GDS2
  timestamps ⇒ byte-stable artifacts) and `png_exporter.py` metadata pinning.
- `scripts/generate_benchmarks.py` — deterministic + skip-if-unchanged +
  normalized timestamps + git-ignored `.generation_meta.json` sidecar;
  `scripts/check_benchmarks.py` — provenance-equality + multi-line README rows.
- Regenerated deterministic benchmark artifacts (gds/png/json/verification × 4).
- `src/textlayout/acceptance.py`, `scripts/generate_acceptance.py`,
  `examples/acceptance/{A_infeasible_5mhz_lc,B_feasible_6ghz_resonator,C_idc_autosize_0p6pf}`.
- Tests: `test_solver_execution.py`, `test_acceptance_physics.py`,
  `test_polygon_drc.py`, `test_product_docs.py` (to adapt to current README).
- `pyproject.toml` extras + Spiral/Resonator/SQUID generator entry points;
  CI `quality-gates` job; `.gitignore` (`ci_out/`, `.generation_meta.json`);
  `CLEAN_ROOM_VERIFICATION.md`, `docs/artifact_policy.md`,
  `docs/public_gpt_action_deployment.md`, `REFERENCES.md`/`docs/openapi_usage.md` additions.
- `plugins/text-to-gds/**` — generated mirror; **not hand-merged**, regenerated
  via `scripts/bundle_plugin.py` after the merge.

**Known intent conflict, resolved explicitly:** main committed
`examples/benchmarks/*/.generation_meta.json`; the stash git-ignores them
because they hold real wall-clock timestamps (churn on every regeneration).
Resolution: follow the stash (untrack + ignore) — committed provenance lives in
the normalized blocks inside `output.json`/`verification.json` instead. This
reverses a decision made earlier on 2026-07-02 and is noted in PROGRESS.md.

## Merge log

(filled in as Phase B executes)
