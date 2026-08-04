# macos platform certification

<!-- GENERATED_CURRENT_STATUS: scripts/platform/verify_platform.py; do not hand-edit. -->

**Evidence source:** `out/platform/macos_arm64.json`
**Git SHA:** `96c4c2b6e44eabf53f7c05496c88b9c010151e4b`
**Real execution:** `True`
**Support state:** `CORE_CERTIFIED`
**Core pass:** `True`

## Host

| Field | Value |
| --- | --- |
| OS | Darwin 24.5.0 |
| Architecture | arm64 |
| WSL detected/version | False / None |
| WSL distribution | not applicable |
| Repository filesystem | not recorded |
| Solver root/filesystem | /Users/lu/.local/share/textlayout / not recorded |

## Core runs

| Python | Tests | Commands | Deterministic IDC | Result |
| --- | --- | --- | --- | --- |
| 3.11.15 | 1891 passed / 0 failed / 11 skipped | 14/14 passed | True | PASS |
| 3.12.13 | 1891 passed / 0 failed / 11 skipped | 14/14 passed | True | PASS |

## External solvers

| Solver | Support | Evidence stage | Version | Identity |
| --- | --- | --- | --- | --- |
| FasterCap | `UNTESTED` | `NOT_INSTALLED` | unknown | `not installed` |
| FastHenry | `UNTESTED` | `NOT_INSTALLED` | unknown | `not installed` |
| openEMS | `UNTESTED` | `NOT_INSTALLED` | unknown | `not installed` |
| Palace | `UNTESTED` | `NOT_INSTALLED` | unknown | `not installed` |
| JoSIM | `UNTESTED` | `NOT_INSTALLED` | unknown | `not installed` |

## Certification boundary

Core certification covers locked installation, imports, CLI/API, deterministic DSL/layout/GDS, KLayout readback, verification, tests, static checks, documentation gates, and package build.
External solver certification requires separate execution, solver-owned output parsing, and convergence evidence. A found binary or passing probe is only `PROBE_PASS`.
