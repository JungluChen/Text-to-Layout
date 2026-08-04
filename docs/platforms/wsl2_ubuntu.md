# wsl2 platform certification

<!-- GENERATED_CURRENT_STATUS: scripts/platform/verify_platform.py; do not hand-edit. -->

**Evidence source:** `out/platform/wsl2_ubuntu.json`
**Git SHA:** `c47c31d118a7bbcb4c6d8e80da7a42a0175a533d`
**Real execution:** `False`
**Support state:** `UNTESTED`
**Core pass:** `False`

## Certification blocker

WSL2 clean-room execution is blocked: this report was generated on Darwin arm64, not inside WSL. Run 'bash scripts/platform/verify_wsl.sh' from Ubuntu on WSL2.

This document is an explicit non-certification record. Ubuntu CI is not WSL2 evidence.

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
| not executed | n/a | n/a | n/a | BLOCKED |

## External solvers

| Solver | Support | Evidence stage | Version | Identity |
| --- | --- | --- | --- | --- |
| none executed on this host | `UNTESTED` | `NOT_INSTALLED` | unknown | n/a |

## Certification boundary

Core certification covers locked installation, imports, CLI/API, deterministic DSL/layout/GDS, KLayout readback, verification, tests, static checks, documentation gates, and package build.
External solver certification requires separate execution, solver-owned output parsing, and convergence evidence. A found binary or passing probe is only `PROBE_PASS`.
