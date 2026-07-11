# Troubleshooting Palace + Gmsh

## Installation

- **`wsl` not found / distribution missing** — install WSL Ubuntu
  (`wsl --install -d Ubuntu`), then rerun
  `uv run python scripts/external/install_palace.py`.
- **Spack build failure** — inspect the retained logs at
  `out/toolchain/palace_install.stdout.txt` and
  `out/toolchain/palace_install.stderr.txt`. The Spack stage lives in
  `.tools/palace/wsl-cache` inside the repository. Package sources, user
  caches, and `build-stage/` logs are retained there for diagnosis.
- **`Gmsh 4.15.2 is required`** — run `uv sync --all-extras` first; the
  installer refuses to proceed with an unpinned mesh runtime.
- **Source archive SHA-256 mismatch** — the pinned Palace archive under
  `.tools/external/sources/` is stale or truncated; delete it and rerun the
  installer, which re-downloads and re-verifies it against
  `external_tools/registry.toml`.

## Execution

- **`check_palace.py` stays at `INSTALLED`** — the smoke test has not
  passed. Run `uv run python scripts/external/run_palace_smoke.py` and read
  `out/toolchain/palace_smoke/palace.stderr.txt` on failure.
- **Palace returns a non-zero exit code** — the run directory retains
  `palace.stdout.txt` / `palace.stderr.txt`; a config or mesh path problem
  is reported there verbatim.
- **`SIMULATION_INVALID` with `ambiguous_mode_identity`** — two candidate
  eigenmodes could not be distinguished by frequency continuity, regional
  energy distribution, and resonator localization. This is a deliberate
  refusal, not a bug: do not hand-pick a mode index.
- **`CONVERGENCE_FAILED`** — the solve executed and parsed but an AMR or
  domain-convergence gate failed; `convergence.json` lists every gate with
  its measured value and threshold.
- **MPI errors inside WSL** — verify `mpirun --version` works in WSL; the
  Spack-installed Palace uses the environment's MPI. Reduce `--processes`
  to 1 to isolate MPI from solver issues.

## Honesty rules

A downloaded archive is not an installation; an installation is not solver
evidence. Only parsed Palace-owned output with passing gates is reported as
`SIMULATION_EXECUTED`, and promotion to `PHYSICS_VERIFIED` additionally
requires an independent reference artifact — the requested design frequency
never counts as one.
