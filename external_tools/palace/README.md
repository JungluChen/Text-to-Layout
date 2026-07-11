# Palace external tool boundary

Text-to-Layout uses Palace 0.17.0 as an optional external Apache-2.0 solver.
Palace is not copied into `src/` and is not bundled in the Python wheel.

The committed `spack.yaml` requests a CPU eigenmode-capable build with ARPACK
and SuperLU_DIST. On Windows, `install_palace.py` runs the pinned Spack release
inside WSL Ubuntu and installs Palace plus its runtime dependencies under the
ignored `.tools/palace/spack-opt` directory. Spack's transient manager and
build cache live in native WSL storage for usable filesystem performance.

```bash
uv run python scripts/external/install_palace.py
uv run python scripts/external/check_palace.py
uv run python scripts/external/run_palace_smoke.py
uv run python scripts/external/uninstall_palace.py
```

The installer verifies the Palace source-archive SHA from
`external_tools/registry.toml`, the exact Palace and Spack commits, Gmsh
4.15.2, the reported Palace version, and the installed executable SHA-256.
Re-running it reuses a valid installation. `--force` rebuilds it.

The smoke case is Palace's official `examples/cavity2d` eigenmode example at
the pinned Palace commit. Its mesh is downloaded by immutable URL and checked
against the committed SHA-256 before execution. A downloaded input or an
installed executable is not solver evidence; only a zero-return Palace run
with parsed and hashed outputs advances the checker to `SMOKE_TEST_PASSED`.
