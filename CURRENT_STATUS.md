# Current Status

**Scope note:** this file covers the legacy `examples/benchmarks/` analytical
packets specifically (see "Benchmark readiness" below) — a different, older
artifact set than the solver-backed `examples/showcase/` examples described in
[README.md](README.md). "No benchmark is PHYSICS VERIFIED" below is about
`examples/benchmarks/`; it does not contradict the showcase examples' real
`PHYSICS_VERIFIED` claims.

For live, generated (never hand-edited) quality-gate numbers, run
`python scripts/generate_project_status.py` and read
[PROJECT_STATUS.md](PROJECT_STATUS.md) — the hard-coded snapshot that used to
live in this section went stale (it claimed "726 passed, 0 failed" long after
the suite had grown past 1000 tests) and has been replaced by that pointer.

## Clean install (fresh virtual environment)

`uv venv` + `uv pip install -e .` into an isolated venv, then:

- `import textlayout`, `import text_to_gds` — OK
- `textlayout --help` — OK
- `textlayout verify examples/benchmarks/01_idc_0p6pf/layout.json` — structured JSON
- `textlayout generate … --out out/idc` — produces gds/svg/png/json + sidecars
- API (`/health`, `/openapi.json`, `/layout/research|generate|verify|report`) — all return JSON; OpenAPI 3.1 with 9 paths

## Honesty invariants (enforced)

- **No benchmark is PHYSICS VERIFIED.** No solver has been executed; all electrical
  values are `ANALYTICAL ONLY`.
- **No benchmark is FABRICATION READY.**
- The 5 MHz LC resonator is **INFEASIBLE / NOT GENERATED** (correct physics:
  LC = 1.013×10⁻¹⁵ s²; L = 10 nH & C = 100 pF → 159 MHz, not 5 MHz).
- `check_benchmarks.py` fails on stale provenance, missing GDS behind an image,
  `physics_verified` without `solver_executed`, any `fabrication_ready`, the old
  5 MHz table, or an ambiguous "PASS" in the README.

## Benchmark readiness

| Benchmark | Geometry | Simulation | Evidence | Fabrication |
|---|---|---|---|---|
| IDC, CPW, Spiral, Quarter-wave | GEOMETRY PASS | SIMULATION INPUT PREPARED (Level 2) | ANALYTICAL ONLY | NOT READY |
| SQUID | GEOMETRY PASS (candidate) | NOT READY (no foundry JJ stack) | ANALYTICAL ONLY | NOT READY |
| 5 MHz LC | NOT GENERATED | NOT APPLICABLE | INFEASIBLE | NOT APPLICABLE |

## Known limitations

- No EM solver has been executed; Level 3+ is not reached for any benchmark.
- `textlayout verify` (CLI) returns the flat geometry/process report
  (`status/checks/warnings/errors`); the full separated schema
  (analytical/simulation/physics/fabrication evidence) is produced by the
  benchmark pipeline (`generate_benchmarks.py`), which also runs research and
  simulation preparation.
- Generated GDS bytes are not bit-reproducible (gdsfactory assigns a unique
  top-cell name per build); provenance keys on the `layout.json` hash instead.
- The legacy `text-to-gds` MCP server (`.mcp.json`) is a stdio server for Claude
  Desktop, not a `--help` CLI. See [docs/plugin_design.md](docs/plugin_design.md).
