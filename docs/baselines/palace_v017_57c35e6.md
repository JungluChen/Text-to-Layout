# Baseline: Palace 0.17 milestone at `57c35e6`

Recorded before correcting the Palace 0.17 verification semantics and
executing the pinned toolchain. The environment snapshot is
`out/baseline/environment.json`; the JUnit report is
`out/baseline/pytest.xml`.

| Check | Result |
| --- | --- |
| Starting commit | `57c35e6b8900a777706d602849064280ef1637b4` |
| `uv sync --all-extras` | OK (219 packages) |
| `uv run pytest -q` | **1690 passed, 0 failed, 2 skipped** |
| JUnit vs `PROJECT_STATUS.md` | matched after regenerating the status manifest (commit `ee60c54`) |
| `uv run ruff check .` | All checks passed |
| `uv run mypy src/textlayout` | Success: no issues found in 163 source files |
| `uv build` | `text_to_gds-0.3.0` wheel + sdist |
| `scripts/check_project_claims.py` | passed |
| `git diff --exit-code` | clean after the status-manifest commit |

## Environment

- Windows 11 Home 10.0.26200; WSL 2 Ubuntu 24.04.1 LTS (default distribution)
- Python 3.12.10 (Windows host), uv 0.11.21
- Gmsh 4.15.2 (pinned `mesh` extra)
- Palace 0.17.0 pinned at `12d8069afb5aa9e169a17e303d735e120968e9f2`
  (Spack 1.1.0 installation in progress at baseline time)
- Open MPI 4.1.6 in WSL; GCC/GFortran 13.3.0
- CPU: 11th Gen Intel Core i7-11800H, 16 logical cores; 11 GB RAM visible in WSL
- Disk: 117 GB free on `C:`, ~934 GB free in the WSL ext4 volume

## Known state carried into this milestone

- The Palace 0.16 historical benchmark records under
  `examples/solver_benchmarks/` are preserved verbatim and must not change.
- `out/palace_resonator_v017/` does not exist yet; no Palace 0.17 solve has
  been executed in this repository.
