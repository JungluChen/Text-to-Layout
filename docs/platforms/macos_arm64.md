# macOS arm64 core certification

**Evidence status:** CORE CERTIFIED — external numerical solvers are not certified.

This record covers the open-source Python/core workflow only. It was assembled
from machine-generated Doctor 2.0 JSON and JUnit XML reports. It does not claim
electromagnetic solver execution, numerical convergence, physics signoff, or
fabrication readiness.

## Environment

| Field | Value |
| --- | --- |
| Date | 2026-08-04 (Asia/Shanghai) |
| Tested git SHA | `454e7c6f94829215e9b97d5e1ab549021a202592` |
| Machine | Apple Silicon, `arm64` |
| OS | macOS 15.5, build 24F74 |
| Python | CPython 3.11.15 and CPython 3.12.13 |
| Environment manager | uv 0.12.1; `uv.lock` used with `--frozen` |
| Package | text-to-gds 0.3.0, editable checkout |
| Core layout | gdsfactory 9.43.0; KLayout Python API 0.30.9 |
| Workflow/schema | LangGraph 1.2.7; Pydantic 2.12.5; NumPy 1.26.4 |

Python 3.12 ran in an isolated ignored environment under `out/audit/`; the
normal Python 3.11 environment was not replaced.

## Commands and results

Both Python versions ran the following core path:

```bash
uv sync --frozen --dev
uv run textlayout doctor --json
uv run textlayout prompt \
  "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap" \
  --out out/audit/macos_<python>_prompt
uv run textlayout verify examples/benchmarks/01_idc_0p6pf/layout.json
uv run pytest --junit-xml=out/audit/macos_<python>_test_report_1.xml
uv run pytest --junit-xml=out/audit/macos_<python>_test_report_2.xml
uv run ruff check .
uv run ruff format --check .
uv run mypy src/textlayout
uv build
uv run python scripts/validate_readme_claims.py
uv run pytest tests/textlayout_suite/test_api.py
```

For Python 3.12, each command used an explicit isolated
`UV_PROJECT_ENVIRONMENT` and `--python 3.12` during sync.

| Gate | Python 3.11 | Python 3.12 |
| --- | --- | --- |
| Locked sync | PASS | PASS |
| Doctor core checks | PASS | PASS |
| Natural-language IDC generation | PASS; solver honestly skipped | PASS; solver honestly skipped |
| Geometry verification | PASS; analytical-only warning | PASS; analytical-only warning |
| Full suite, run 1 | 1,871 passed; 13 skipped | 1,871 passed; 13 skipped |
| Full suite, run 2 | 1,871 passed; 13 skipped | 1,871 passed; 13 skipped |
| Ruff lint / format | PASS / PASS | PASS / PASS |
| Strict mypy | 177 source files PASS | 177 source files PASS |
| sdist + wheel build | PASS | PASS |
| README evidence claims | PASS | PASS |
| API suite | 12 passed | 12 passed |

## Solver and physics capability

Doctor launched no real external solver because none was installed. All absent
tools were reported as `MISSING`, never as executed evidence.

| Capability | Backend | Version | Result |
| --- | --- | --- | --- |
| IDC electrostatics | FasterCap/FastCap | not installed | NOT_INSTALLED |
| CPW FDTD | openEMS + CSXCAD + Octave + scikit-rf | incomplete/not installed | NOT_INSTALLED |
| Spiral PEEC | FastHenry | not installed | NOT_INSTALLED |
| Eigenmode FEM | Palace + Gmsh + meshio | meshio 5.3.5 only | INCOMPLETE |
| Josephson transient | JoSIM | not installed | NOT_INSTALLED |
| Josephson harmonic balance | WRspice/ngspice | not installed | NOT_INSTALLED |

## Failures, skips, and limits

- No test failed in either repeated run.
- Thirteen tests skipped because optional external integrations or a WSL host
  were absent.
- Each full run emitted 518,005 warnings. Most are repeated Pydantic warnings
  caused by NumPy `bool_` values in large showcase tests; this is tracked as
  technical debt, not hidden as a pass-quality claim.
- The prompt produced deterministic GDS/report artifacts but stopped at
  `SKIPPED_SOLVER_ABSENT`. Its capacitance is an analytical estimate only.
- CI now schedules the same core matrix on GitHub's `macos-15` arm64 runner for
  Python 3.11 and 3.12. This local record does not claim that the new remote CI
  jobs have already completed.

## Certification boundary

The CLI, API, deterministic DSL/layout generation, KLayout readback,
verification, reports, measurement parser tests, optimizer tests, and PDK tests
are supported by this evidence on macOS arm64. Real solver execution,
convergence, cross-solver agreement, measurement calibration, and fabrication
readiness are outside this certification.
