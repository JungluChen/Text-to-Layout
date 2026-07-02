# Clean-Room Verification

**Result: local CLI / API / plugin-style verification PASS.**

This document records a from-scratch install-and-verify run of Text-to-Layout in
a clean environment. It establishes that the project installs, the CLI works, the
API serves valid JSON/OpenAPI, the benchmarks regenerate and pass a strict audit,
and the test suite is green — **on a local machine**.

> This is **local** plugin-style verification. It does **not** claim a public
> GPT Action deployment; no public HTTPS endpoint was deployed or tested. See
> [docs/public_gpt_action_deployment.md](docs/public_gpt_action_deployment.md)
> for the path to a public endpoint.

## Environment

| Item | Value |
| --- | --- |
| Python | 3.11+ (clean-room), 3.12 (development) |
| OS | Windows 11 / Linux (CI matrix: ubuntu-latest, windows-latest) |
| Package (CLI) | `textlayout` |
| Distribution | `text-to-gds` 0.2.0 (`pyproject.toml`) |
| Install tool | `pip` or `uv` |

### Dependency highlights

Core runtime: `gdsfactory`, `klayout`, `pydantic` v2, `matplotlib`, `fastapi`,
`uvicorn`, `numpy`, `pillow`. Optional groups: `dev` (pytest, ruff, mypy),
`api`, `solvers` (scikit-rf), `docs` (mkdocs). Native solvers (FasterCap,
FastHenry, openEMS) are external binaries, installed separately; the workflow
detects them and degrades gracefully when absent.

## Steps verified

| Step | Command | Result |
| --- | --- | --- |
| Install | `pip install -e .` | PASS |
| CLI help | `textlayout --help` | PASS |
| CLI verify | `textlayout verify examples/benchmarks/01_idc_0p6pf/layout.json` | PASS |
| CLI generate | `textlayout generate examples/benchmarks/01_idc_0p6pf/layout.json --out out/idc` | PASS |
| API serve | `textlayout serve` | PASS |
| API health | `GET /health` | PASS (JSON, `status: ok`) |
| API schema | `GET /openapi.json` | PASS (valid JSON, OpenAPI 3.x) |
| Benchmark regen | `python scripts/generate_benchmarks.py` | PASS |
| Benchmark audit | `python scripts/check_benchmarks.py --strict` | PASS |
| Acceptance regen | `python scripts/generate_acceptance.py` | PASS |
| Test suite | `pytest` | PASS (see below) |
| Lint | `ruff check .` | PASS |

## Test suite

A prior clean-room baseline reported **726 passed, 8 skipped**. This branch adds
the physics-fit acceptance suite, the solver-execution suite, and determinism
checks; the current local result is recorded in the project's final report and
reproduced by CI.

### Skipped tests

Skips are honest and expected — they gate on optional, externally-installed
solvers and Python packages that are not present in a minimal clean-room install:

- External native solvers (FasterCap, FastHenry, openEMS, Elmer, Palace) — slow
  external-solver tests are skipped unless `TEXT_TO_GDS_RUN_EXTERNAL=1`.
- Optional Python backends (scqubits, scikit-rf, qiskit-metal, pyEPR, pyaedt) —
  guarded with `importlib.util.find_spec` skips when not installed.

No skip hides a failure; each is a deliberate "solver/library not present" gate.

## Reproducibility

Regenerating the benchmarks twice in a row produces no git diff:

```bash
python scripts/generate_benchmarks.py            # reproducible; skips unchanged
python scripts/generate_benchmarks.py --force    # byte-identical for a pinned toolchain
git diff --quiet examples/benchmarks/ && echo "clean"
```

Details and the (documented) toolchain-version caveats for GDS/PNG bytes are in
[docs/artifact_policy.md](docs/artifact_policy.md).

## Known limitations

- The generic technology is **not** a foundry PDK.
- All benchmark physical values are **analytical estimates**, not solver or
  measurement evidence — **no benchmark is PHYSICS VERIFIED or FABRICATION READY**.
- Native EM/extraction solvers are not bundled; execution paths are exercised
  only when the solver is installed (CI runs the graceful solver-missing paths).
- openEMS execution is post-processing-only in `textlayout`: a runnable CSXCAD
  model generator is a documented TODO; until then, openEMS comparison requires a
  Touchstone produced externally (or via the legacy `text_to_gds.openems_runner`).
- Public GPT Action usage requires a public HTTPS deployment, which is documented
  but not performed in this repository.
