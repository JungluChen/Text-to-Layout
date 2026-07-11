# Installing Palace 0.17.0 + Gmsh 4.15.2

Palace and Gmsh are optional external tools. They are not bundled in the
`text-to-gds` wheel and installing them does not by itself make any result
physics-verified.

## Pins

| Component | Pin | Where it is enforced |
| --- | --- | --- |
| Palace | `0.17.0`, commit `12d8069afb5aa9e169a17e303d735e120968e9f2` | `external_tools/registry.toml`, `scripts/external/_palace_common.py` |
| Gmsh | `4.15.2` | `mesh` optional dependency in `pyproject.toml`, validated at runtime |
| Spack | `1.1.0` + pinned packages commit | `scripts/external/_palace_common.py` |
| Spack environment | committed | `external_tools/palace/spack.yaml` |

`tests/textlayout_suite/test_palace_toolchain_pins.py` fails if these sources
drift apart.

## Windows (WSL Ubuntu)

Palace does not build natively on Windows. The installer runs the pinned
Spack release inside WSL Ubuntu.

The pinned **source archives** (verified by SHA-256) stay under the git-ignored
`.tools/external/sources` tree, and the small **install-identity record**
(`install.json`, which records the Palace version, executable path, and its
SHA-256) stays under `.tools/palace`. Those are the auditable, persistent
artifacts kept inside the repository's ignored tool tree.

The Spack clone, environment, caches, transient build stage, and the installed
binaries live on native WSL ext4 under `$HOME/.cache/textlayout-palace`
(overridable with `TEXTLAYOUT_PALACE_NATIVE_ROOT`). Native ext4 is required for
viable performance: on the `/mnt/c` 9p mount the many-small-file operations of
autotools configure and package installs (gettext installs ~1,760 tiny `.po`
files; MFEM and PETSc install thousands of headers) are an order of magnitude
slower and stall. Those binaries are still git-ignored, never committed, never
merged into `src/`, and are fully reproducible from the pinned sources — so the
licensing and isolation boundary is preserved while the build completes in
reasonable time.

Prerequisites inside WSL Ubuntu: `gcc g++ gfortran git make python3` and an
MPI implementation providing `mpirun` (`sudo apt install build-essential
gfortran git openmpi-bin libopenmpi-dev`).

```bash
uv sync --all-extras
uv run python scripts/external/install_palace.py
uv run python scripts/external/check_palace.py
```

A successful installation writes `out/toolchain/palace_install.json` and
`.tools/palace/install.json` recording the Palace version, the executable
location inside WSL, and its SHA-256. `check_palace.py` reports at least
`INSTALLED`. Re-running the installer reuses a valid installation; pass
`--force` to rebuild.

## Validate the installation

```bash
uv run python scripts/external/run_palace_smoke.py
uv run python scripts/external/check_palace.py
```

The smoke case is Palace's official `examples/cavity2d` eigenmode example at
the pinned commit. Only a zero-return Palace run with parsed, hashed
`eig.csv` and `domain-E.csv` outputs advances the checker to
`SMOKE_TEST_PASSED`.

## Run the CPW quarter-wave benchmark

```bash
uv run textlayout simulate palace-resonator \
  --out out/palace_resonator_v017
```

This executes Palace with native adaptive mesh refinement, tracks the
resonator mode across AMR iterations, runs four independent
computational-domain sweeps, and writes `canonical_evidence.json` under the
repository's existing evidence schema. The result is limited to
`SIMULATION_EXECUTED` even when every convergence gate passes, because no
independent reference artifact exists for this design.

Make targets: `make setup-palace`, `make check-palace`, `make smoke-palace`,
`make benchmark-palace`.
