# Internal audit — 2026-07 consistency + cQED upgrade

Snapshot taken before Sprint 1. Not a permanent doc — superseded by
`PROJECT_STATUS.md` once Sprint 1 lands.

## Product vs legacy package

- **Product package:** `src/textlayout` (CLI `textlayout`, FastAPI app, all new
  work). Confirmed current — this is where `epr`, `yield_model`,
  `chip_lattice`, `pdk`, `measurement` already live (added in a prior session).
- **Legacy package:** `src/text_to_gds` — explicitly frozen per its own
  `__init__.py` docstring and `docs/legacy/ARCHITECTURE_text_to_gds.md`. Ships
  93 MCP tools via `server.py`, 5 additional `text-to-gds-*` CLI entry points.
  Has its own older `epr.py`, `backends/pyepr_backend.py`, and `pdk/` module —
  these predate and are superseded by `textlayout.epr` / `textlayout.pdk`; left
  alone per the "frozen legacy" convention already documented.

## Concrete inconsistencies found

1. **Version mismatch.** `pyproject.toml` says `version = "0.2.0"`.
   `IMPLEMENTATION_REPORT.md` (dated 2026-06-26) says
   `Version: 0.3.0 (was 0.2.0)`. The package was never actually bumped.
2. **Package description contradicts the documented architecture.**
   `pyproject.toml`'s `description` field ("Local-first MCP tools for agentic
   GDS generation, DRC, and superconducting circuit layout") describes the
   *legacy* `text_to_gds` MCP surface, while `ARCHITECTURE.md` and
   `docs/ARCHITECTURE.md` both state `textlayout` is the supported product
   path. A reader of `pyproject.toml` alone would draw the wrong conclusion
   about which package is current.
3. **`CURRENT_STATUS.md` test counts are stale.** It claims
   `726 passed, 8 skipped, 0 failed` as "last verified 2026-06-30". A fresh
   `pytest` run today: **1032 passed, 8 skipped, 28 failed**. The failed count
   is not a regression from this session's work — it is the pre-existing
   upstream baseline (`test_solver_execution.py`,
   `test_simulator_bootstrap.py`, several `tests/test_*_matches_*.py` files
   requiring solvers/tools not installed in this environment) — but the doc's
   "0 failed" claim is simply wrong for this checkout and was likely measured
   in an environment with more optional tooling installed.
4. **`PHYSICS_COMPILER_STATUS.md`** describes only the legacy
   `src/text_to_gds` physics-graph work (2026-06-24-era); it predates the
   `textlayout` product path entirely and is not updated for anything in this
   session or the prior one.

## What already existed before this session (from the prior /loop)

- `textlayout.epr`: `AnalyticalEPRBackend` (status `ANALYTICAL_ONLY`),
  `PyEPRBackend` (status `SKIPPED_SOLVER_ABSENT`), coherence estimator
  (`1/Q = sum(p*tanδ)`, `T1 = Q/omega`), illustrative materials DB, CLI
  `textlayout epr` / `verify --include-epr`.
- `textlayout.yield_model`: JJ/SQUID physics, seeded Monte Carlo yield,
  CLI `textlayout yield jj` / `yield qubit-array`.
- `textlayout.chip_lattice`: collision taxonomy, Monte Carlo collision yield,
  greedy retune optimizer, CLI `textlayout chip analyze` / `chip optimize`.
- `textlayout.pdk`: PDK schema (layers, substrate, junction_process),
  YAML loader, `pdk_to_technology()` bridge, two shipped PDKs
  (`generic_2metal_pdk`, `example_superconducting_pdk`, both
  `foundry_validated: false`), density DRC hook, LVS interface stub, CLI
  `textlayout pdk list` / `pdk info`.
- `textlayout.measurement`: residual comparison, correction-factor fit,
  CLI `textlayout measurement compare` / `measurement calibrate`.
- `examples/real_cqed_loop.py`: 7-step end-to-end demo wiring all of the above.

## Gaps this sprint set targets

- No machine-readable, single-source-of-truth status manifest — Sprint 1.
- EPR status vocabulary uses the project's shared 3-value enum
  (`ANALYTICAL_ONLY`/`SIMULATION_EXECUTED`-style), not the 5-value
  EPR-specific vocabulary requested here
  (`EPR_INPUT_PREPARED`/`FIELD_ENERGY_IMPORTED`/`EPR_ANALYTICAL_ONLY`/
  `EPR_EXECUTED`/`EPR_SKIPPED_SOLVER_ABSENT`) — Sprint 2.
- EPR is not yet wired into the main `textlayout prompt` design-report loop
  (only `epr`/`verify --include-epr` standalone commands) — Sprint 2.
- PDK records `foundry_validated: bool` but no `calibration_status` enum,
  no file hash, and reports don't embed PDK provenance — Sprint 4.
- No hardened openEMS CPW/resonator full-wave path with real CSX export +
  Touchstone parsing wired end to end in `textlayout` (exists partially in
  legacy `text_to_gds`/`simulation/`, and `textlayout.simulation.open_source`
  prepares openEMS input, but execution+parse is not fully proven here) —
  Sprint 5.

## Test commands (current)

```bash
.venv/bin/python -m pytest tests/textlayout_suite -q   # product suite: 391 passed, 18 pre-existing failures
.venv/bin/python -m pytest tests/ -q                    # full repo: 1032 passed, 8 skipped, 28 failed
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy src/textlayout
.venv/bin/python scripts/validate_readme_claims.py       # 19 pre-existing failures (showcase artifact gaps)
.venv/bin/python scripts/check_benchmarks.py --strict
```
