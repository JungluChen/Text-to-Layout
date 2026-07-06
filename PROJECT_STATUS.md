# Project Status

Generated: 2026-07-06T02:25:20+00:00 — by `scripts/generate_project_status.py`. Do not hand-edit; this file is a rendering of `out/evidence/project_status.json`.

- **Package version:** `0.3.0`

## CLI commands (introspected from the real parser)

- `textlayout chip` — subcommands: `analyze`, `optimize`
- `textlayout doctor`
- `textlayout epr`
- `textlayout generate`
- `textlayout measurement` — subcommands: `calibrate`, `compare`
- `textlayout pdk` — subcommands: `info`, `list`
- `textlayout prompt`
- `textlayout serve`
- `textlayout verify`
- `textlayout yield` — subcommands: `jj`, `qubit-array`

## Showcase evidence

- Total examples: 6
- Solver-backed (`PHYSICS_VERIFIED`/`SIMULATION_EXECUTED`): 01_idc_0p6pf, 02_cpw_50ohm, 03_idc_cpw_test_structure, 04_spiral_inductor_3nh, 05_quarter_wave_resonator_6ghz
- Skipped (`SKIPPED_SOLVER_ABSENT`): (none)
- Analytical only: 06_research_test_chip

## Tests

- **465 passed, 0 failed, 0 skipped** (source: pytest tests/textlayout_suite)

## PDK / fabrication readiness

- **NOT_FABRICATION_READY: no foundry-validated PDK is present**

| PDK | Version | Foundry-validated | Source |
| --- | --- | --- | --- |
| example_superconducting_pdk | 0.1.0 | False | Illustrative example combining published order-of-magnitude Nb/Al-on-Si process figures; NOT a real foundry PDK. |
| generic_2metal_pdk | 0.1.0 | False | Mirrors the built-in generic_2metal Technology; illustrative only. |

## EPR / coherence support

- CLI command available: True (also `--include-epr` on `prompt`/`verify`)
- Statuses: `EPR_ANALYTICAL_ONLY`, `EPR_EXECUTED`, `EPR_INPUT_PREPARED`, `EPR_SKIPPED_SOLVER_ABSENT`, `FIELD_ENERGY_IMPORTED`
- Default backend: analytical scaling model (EPR_ANALYTICAL_ONLY); a field-solver EPR (pyEPR/HFSS or Palace energies) is imported, never fabricated
- Field-solver verified by default: **False**

## Measurement calibration support

- `measurement compare`: True · `measurement calibrate`: True
- Committed fixtures are synthetic: **True** — All committed measurement data is synthetic. Real fabrication confidence requires correlation against measured devices.

## Known limitations (from README)

- The generic technology is not a foundry PDK. A richer, still-illustrative PDK schema and example (`textlayout pdk list` / `textlayout pdk info`) is documented in [docs/pdk_abstraction.md](docs/pdk_abstraction.md) — real fabrication still requires a foundry-qualified PDK.
- Legacy `examples/benchmarks/` IDC capacitance is an analytical starting estimate; showcase examples 01 and 03 have the solver evidence stated above.
- The FasterCap model uses zero-thickness panels and an effective dielectric — a correlation model, not signoff; it requires mesh convergence and finite-thickness/full-wave cross-checks.
- Full-chip density, antenna, slot, enclosure, LVS, and process-specific DRC are outside the clean plugin package today.
- The next component should be promoted only after typed ports, extraction, literature comparison, and a reproducible benchmark are complete.
- **PHYSICS_VERIFIED currently exists for showcase examples 01 and 04, plus the embedded IDC region of example 03.** Other scopes remain analytical, prepared, or honestly skipped unless their solver evidence says otherwise.
- **Nothing in this repository is FABRICATION READY** — every layout requires process-specific DRC, EM cross-check, measurement planning, and expert review.
