# Palace work — measured baseline

Every command below was executed in this environment and its **exact** output is
recorded. Nothing here is copied from a previous report or from the repository's
own claims: the committed test count was treated as unverified until reproduced.

- **Baseline commit:** `3bdc7513d853bfbaafb39f316ab0ada8d4b54434`
- **Working tree at baseline:** clean (tracked files)
- **Date:** 2026-07-10

## Environment

| Component | Version / location |
|---|---|
| Python | 3.12.10 (MSC v.1943, 64-bit) |
| OS | Windows-11-10.0.26200-SP0 |
| Gmsh (Python API) | **4.15.2** |
| Gmsh (CLI) | `.venv/Scripts/gmsh.bat` — not on `PATH` |
| **Palace** | **NOT FOUND** — absent from Windows `PATH` and from WSL `PATH` |
| MPI | Open MPI 4.1.6, via WSL `/usr/bin/mpirun`. No `mpiexec`/`mpirun` on the Windows `PATH`. |
| GPU | NVIDIA GeForce RTX 3060 Laptop GPU (visible to `nvidia-smi`) |
| Spack | absent; no `palace` package in the WSL apt index |

### What this means for Palace

Palace cannot be executed here, and no attempt is made to pretend otherwise. It
is not packaged for apt, Spack is not installed, and a from-source build pulls in
MFEM, PETSc/SLEPc, libCEED and a full MPI toolchain — hours of work that this
environment cannot validate. Every Palace-dependent phase therefore ends in an
honest `SKIPPED_SOLVER_ABSENT`, never in a synthesised result.

The GPU is present but irrelevant until Palace exists: Palace's GPU support is a
build-time option (`libCEED` + CUDA backend), not a runtime switch.

## Baseline quality gates

| Command | Exact result |
|---|---|
| `uv run pytest -q` (first run) | **2 failed, 1444 passed, 6 skipped** in 171.97s |
| `uv run pytest -q` (after removing stray, see below) | **1446 passed, 6 skipped** in 166.91s |
| `uv run ruff check .` | `All checks passed!` |
| `uv run mypy` (configured scope: `src/textlayout`) | `Success: no issues found in 134 source files` |
| `uv build` | built `text_to_gds-0.3.0.tar.gz` + `text_to_gds-0.3.0-py3-none-any.whl` |
| clean wheel install into a fresh venv | exit 0 |
| `textlayout --version` from that venv | `textlayout 0.3.0` |
| `import textlayout, text_to_gds` from that venv | ok |
| `scripts/build_canonical_evidence.py --check` | `6/6 canonical records are current.` |
| `scripts/generate_project_status.py --check` | `project status artifacts are current.` |
| `scripts/bundle_plugin.py --check` | `plugin bundle is thin and current (0.3.0).` |
| `scripts/validate_readme_claims.py` | `README claim validation passed` |
| benchmark artifact drift | no drift |

`uv run mypy src/` reports 457 errors, but that overrides the configured scope
(`files = ["src/textlayout"]`) and pulls in the legacy `text_to_gds` package,
which mypy deliberately does not check. As CI invokes it — `uv run mypy` — mypy
is clean.

## The baseline was not green, and why

The first full run failed two tests:

```
FAILED tests/textlayout_suite/test_plugin_thin_bundle.py::TestNoCopiedImplementation::test_every_bundled_path_is_allowlisted
FAILED tests/textlayout_suite/test_plugin_thin_bundle.py::TestBundleCheckGate::test_check_passes_on_the_committed_bundle
```

Both were caused by one **untracked** file left in the working tree by an earlier
benchmark run, back when the plugin still contained a full copy of the project:

```
plugins/text-to-gds/examples/benchmarks/04_quarter_wave_resonator/simulation/simulation_manifest.json
```

The thin-bundle guard did exactly its job: it refused to accept a file the
allowlist does not permit. But the failure was reproducible only on a working
tree carrying that leftover. Nothing in the current tree can recreate it — the
plugin no longer ships `scripts/`, and neither `generate_benchmarks.py` nor the
test suite writes under `plugins/` (both were re-run against a cleaned tree to
confirm). Deleting the leftover restores a green suite at **1446 passed**.

This exposed a genuine defect in the guard's own test rather than in the guard:
`test_check_passes_on_the_committed_bundle` inspected the *working tree*, not the
committed bundle its name promises, so any developer with build detritus under
`plugins/` would see a spurious failure. That test is fixed to assert over
`git ls-files` — a copied implementation file is only a repository problem once
it is *committed*. The working-tree check remains in `bundle_plugin.py --check`,
which CI runs before rebuilding, so a committed copy still cannot slip through.

## Reproducing this baseline

```bash
git checkout 3bdc7513
uv run pytest -q
uv run ruff check .
uv run mypy
uv build
uv run python scripts/build_canonical_evidence.py --check
uv run python scripts/generate_project_status.py --check
uv run python scripts/bundle_plugin.py --check
```

Detect the solver stack:

```bash
uv run textlayout doctor          # reports Palace as [missing], honestly
uv run python -c "import gmsh; gmsh.initialize(); print(gmsh.option.getString('General.Version'))"
wsl -e bash -lc "mpirun --version"
```
