# Whole-Project Audit Report

Date: 2026-07-02
Auditor role: Principal EDA Software Architect / Numerical Simulation Reviewer / Clean-Room Code Auditor
Scope: full repository at commit `a87f6b8` (branch `mvp2-trust-hardening`, identical to `main`).

---

## Phase 0 — Baseline (measured, not assumed)

All commands run from a fresh working tree on Windows 11, Python 3.12, uv-managed venv.

| Command | Result |
| - | - |
| `uv run ruff check .` | **All checks passed!** (exit 0) |
| `uv run pytest -q` | **726 passed, 8 skipped** in 74.5 s (exit 0) |
| `uv run pytest --co -q` | collection clean, no errors (exit 0) |
| `uv build` | success (exit 0) |

Warnings observed (non-fatal): pydantic `Field name "schema" shadows an attribute`
in `src/text_to_gds/extracted_device.py:39` and `src/text_to_gds/microwave_validator.py:12`;
starlette TestClient deprecation from the installed FastAPI version.

Note: the earlier memory of a RED suite (2026-06-29 audit) is stale — the collection
error was fixed in subsequent commits. The suite is green at baseline.

### Branch inventory (measured with `git rev-list --count`)

| Branch | vs `main` | Disposition |
| - | - | - |
| `mvp2-trust-hardening` (current) | ahead 0, behind 0 — identical | work continues here; merge to main at end |
| `review-fixes` (local only) | ahead 0, behind 28 — fully merged | delete |
| `codex/evidence-first-layout-plugin` (local + remote) | ahead 0, behind 6 — fully merged | delete local + remote |

No branch carries unmerged commits; "merge other branches into main" reduces to
deleting the fully-merged stale branches.

### Stale bytecode discovery

`src/textlayout/__pycache__/` contains compiled modules with **no corresponding
source in git history or the working tree**: `prompt.py`, `evidence_contract.py`,
`acceptance.py`, `optimization/idc.py`, `workflows/from_text.py`,
`simulation/runners.py`, `ports/validator.py`. These are remnants of an
uncommitted prior session. The features they represent (prompt parser, evidence
contract, IDC optimizer, text workflow) must be (re)built and committed properly.

---

## Phase 1 — Architecture audit

### 1. Package architecture

- **`src/textlayout`** — the clean product path. Layered: `schemas/dsl` (pydantic
  firewall) → `geometry/engine.py` → `verification/` → `exporters/` →
  `workflows/generate.py`, plus `research/` (cited analytical models),
  `simulation/` (FasterCap/openEMS/FastHenry prep + guarded FasterCap execution),
  `backend/` (FastAPI factory), `cli.py`. mypy-strict is scoped to this package
  (`pyproject.toml` `[tool.mypy] files = ["src/textlayout"]`).
- **`src/text_to_gds`** — the legacy MCP-server package (~80 `@mcp.tool()`
  functions in `server.py`, nine backend classes, physics modules). It is large
  but green under tests and is the MCP product surface. **Decision: do not expand
  it; do not delete it in this sprint.** It is marked legacy in docs; `textlayout`
  is the primary path.

### 2. CLI architecture

- `textlayout` (`textlayout.cli:main`) — subcommands `generate`, `verify`, `serve`.
  **Gap:** no `prompt` subcommand (the brief's primary entry point).
- Legacy consoles: `text-to-gds` (MCP stdio server) + four `text-to-gds-*`
  pipeline CLIs. Kept as-is (legacy surface), documented as such.

### 3. API architecture

`textlayout/backend/app.py` is a clean factory with routes
`/health`, `/layout/{generate,research,verify,preview,export,report,simulate,benchmark}`.
Schemas live in `api_models.py`, settings in `settings.py`. Not a god module.
**Gap:** no `POST /layout/from-text`.

### 4. Generator architecture (per-generator inventory)

| Generator | Schema | Impl | Verifier | Example DSL | Benchmark | Tests | Verdict |
| - | - | - | - | - | - | - | - |
| IDC | `schemas/dsl/idc.py` | `generators/idc.py` | yes | `examples/benchmarks/01_idc_0p6pf` | yes | `test_idc_generator.py` | supported |
| CPW | `schemas/dsl/cpw.py` | `generators/cpw.py` | yes | `02_cpw_50ohm` | yes | `test_cpw_generator.py`, golden | supported |
| SpiralInductor | `schemas/dsl/spiral.py` | `generators/spiral.py` | yes | `03_spiral_inductor` | yes | `test_extended_generators.py` | supported |
| QuarterWaveResonator | `schemas/dsl/resonator.py` | `generators/resonator.py` | yes | `04_quarter_wave_resonator` | yes | `test_extended_generators.py` | supported |
| SQUID | `schemas/dsl/squid.py` | `generators/squid.py` | yes | `05_squid_loop` | yes | `test_extended_generators.py` | experimental (JJ placeholders, no foundry stack) |

### 5. Simulation architecture

- `simulation/fastercap.py` — **prepares** FastCap/FasterCap panel+list files
  (metres, Q-panels), **executes** when a binary is found (`shutil.which`),
  captures stdout/stderr to files, **parses** the capacitance matrix with unit
  conversion, and fails safely on ambiguous output. Statuses:
  `input_files_prepared | skipped | failed | executed`. Honest.
- `simulation/open_source.py` — openEMS (CPW, resonator), FastHenry (spiral),
  SQUID plan: **input preparation only**, correctly labeled readiness level 2.
- `simulation/models.py` — `SimulationResult` dataclass with readiness levels 0–5.
- **Gaps:** (a) statuses are lowercase strings, not the required typed evidence
  vocabulary (`PHYSICS_VERIFIED`, `SKIPPED_SOLVER_ABSENT`, …); (b) no
  target-vs-extracted comparison step, so `PHYSICS_VERIFIED` can never be
  produced or, worse, could be claimed informally; (c) no single typed
  per-quantity evidence record shared by CLI/API/tests/reports.
- Legacy `text_to_gds` solver stack (JosephsonCircuits.jl, scqubits, openEMS,
  Palace, Elmer adapters) is out of scope for expansion; its honesty contract
  (`SKIPPED` when unavailable) already exists and is tested.

### 6. Documentation honesty

- README status vocabulary and benchmark table are already conservative
  ("No benchmark is PHYSICS VERIFIED", per-benchmark SIMULATION INPUT PREPARED /
  ANALYTICAL ONLY labels). Good.
- **Gaps:** no `## 30-second demo`; no component support matrix wired to a
  validator; no `scripts/validate_readme_claims.py`; CI does not check claims.
- Untracked debris: `examples/benchmarks/*/.generation_meta.json` and `out/`
  are uncommitted; decide track-or-ignore.

## Weak points & risks (ranked)

1. **No end-to-end text → layout → evidence path** (highest value gap; Phases 3–5).
2. **No typed evidence contract** — honesty currently rests on convention, not
   structure (Phase 2).
3. **No claim-validation CI** — README could silently drift from code (Phase 8).
4. **Stale pycache without sources** — confusing ghost features; clean up.
5. **Two parallel packages** — mitigated by docs, mypy scoping, and freezing the
   legacy surface; full removal is out of scope for this sprint.

## Refactor plan (executed in this sprint)

- Phase 2: `textlayout/evidence.py` — typed `QuantityEvidence` + `EvidenceStatus`
  with structural validation (PHYSICS_VERIFIED impossible without a parsed,
  existing solver-owned output file within tolerance).
- Phase 3: `textlayout/prompt.py` deterministic parser; `textlayout prompt` CLI;
  `POST /layout/from-text`.
- Phase 4: `textlayout/optimization/idc.py` closed-loop analytical tuner.
- Phase 5: evidence mapping over the existing FasterCap prepare/run/parse flow.
- Phase 6: verification already covers the checklist; add explicit invalid-geometry
  regression coverage where missing.
- Phases 7/10: README 30-second demo + support matrix.
- Phase 8: `scripts/validate_readme_claims.py` + CI step.
- Phase 9: tests for all 8 required categories under `tests/textlayout_suite/`.

Files to change: `src/textlayout/{evidence.py,prompt.py,cli.py,optimization/*,
workflows/from_text.py,backend/{app.py,api_models.py},simulation/*}`,
`scripts/validate_readme_claims.py`, `.github/workflows/ci.yml`, `README.md`,
`tests/textlayout_suite/*`, `docs/PROGRESS.md`.
