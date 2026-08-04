# WSL2 Ubuntu platform record

**Evidence status:** NOT_TESTED_ON_PLATFORM.

No WSL2 host was available during the 2026-08-04 improvement loop. This file is
therefore an explicit non-certification record, not a support claim. Historical
solver artifacts elsewhere in the repository are not substituted for a clean
current-platform run.

## Environment and versions

| Field | Evidence |
| --- | --- |
| Date | 2026-08-04 (Asia/Shanghai) |
| Bootstrap git SHA | `a2c50af5c01fe73e45a995886dc1d28d16353141` |
| WSL version | NOT TESTED |
| Ubuntu distribution | NOT TESTED |
| Architecture | NOT TESTED |
| Filesystem placement | NOT TESTED |
| Python/dependency versions | NOT TESTED |
| Solver versions | none observed |

## Prepared, repeatable procedure

The repository provides an idempotent entry point:

```bash
bash scripts/bootstrap_wsl.sh
```

It detects WSL, version, distribution, architecture, and checkout filesystem;
warns when a checkout under `/mnt/c` would be a poor heavy-build location;
uses WSL-native storage for optional solver sources/builds; installs a pinned uv
bootstrap; syncs from `uv.lock` with `--frozen`; and runs doctor, prompt,
verification, and tests.

The non-mutating plan was run twice on macOS:

```bash
bash scripts/bootstrap_wsl.sh --dry-run > out/audit/wsl_bootstrap_dry_run_1.txt
bash scripts/bootstrap_wsl.sh --dry-run > out/audit/wsl_bootstrap_dry_run_2.txt
cmp out/audit/wsl_bootstrap_dry_run_1.txt out/audit/wsl_bootstrap_dry_run_2.txt
```

Result: PASS — byte-identical plans and no created native-root directory. Shell
syntax checks and two repeatable pytest contract tests also passed. This proves
only bootstrap plan determinism, not WSL execution.

## Required certification run

On a clean Windows + WSL2 Ubuntu machine:

```bash
git clone https://github.com/JungluChen/Text-to-Layout.git
cd Text-to-Layout
bash scripts/bootstrap_wsl.sh
uv run textlayout doctor --json > out/platform/wsl2/doctor-final.json
```

Then preserve the Doctor JSON, both full-suite JUnit reports, prompt artifacts,
Ubuntu release, WSL version, git SHA, dependency versions, solver probe results,
failures, and skips. Update this record to `CORE CERTIFIED` only when those
artifacts pass on the exact recorded SHA.

Optional solver flags are intentionally separate because they are large and
need their own smoke/result evidence:

```bash
bash scripts/bootstrap_wsl.sh --with-circuit-solvers
bash scripts/bootstrap_wsl.sh --with-openems
bash scripts/bootstrap_wsl.sh --with-palace
```

Installing or locating a binary is not physics evidence. Doctor must probe it,
and solver-backed claims still require non-empty solver-owned outputs,
convergence, and the repository's evidence gates.

## Current blockers

- No current clean WSL2 machine run.
- No current dependency or solver versions captured on WSL2.
- No current repeated WSL2 full-suite result.
- No real numerical solver was executed as part of this platform record.
