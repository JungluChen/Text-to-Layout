# Palace execution baseline

Captured on 2026-07-11 (Asia/Singapore), before Palace vertical-slice code changes.

## Source state

- Branch: `main`
- Commit: `03c91babee48b0dae5bef93d4a0f37d23219377d`
- Initial worktree: clean and aligned with `origin/main`

## Test-count reconciliation

Historical test totals in `docs/AUDIT_REPORT.md`, `docs/BRANCH_INVENTORY.md`,
`docs/evidence_consistency_baseline.md`, `docs/improvement_baseline.md`, and
`docs/palace_baseline.md` describe different earlier repository snapshots. They
range from 726 passed to 1446 passed and are not counts for this commit.

The current suite was collected and executed from the clean commit above:

```text
$ .venv/Scripts/python.exe -m pytest --collect-only -q
1655 tests collected in 9.79s

$ .venv/Scripts/python.exe -m pytest -q --junitxml=out/palace_execution_baseline/pytest_junit.xml
23 failed, 1624 passed, 8 skipped, 518005 warnings in 156.06s (0:02:36)
```

The counts reconcile exactly: `1655 = 1624 passed + 23 failed + 8 skipped`.
The JUnit `testsuite` attributes are `tests=1655`, `failures=23`, `errors=0`,
`skipped=8`, and `time=154.859`. The fresh report is
`out/palace_execution_baseline/pytest_junit.xml`; the retained console output is
`out/palace_execution_baseline/pytest_console.txt`.

The 23 baseline failures are pre-existing on this commit. They fall into these
groups:

- Missing reference data or PDK inputs: CPW, JJ-stack, JPA, transmon, and
  `ncu_alox_2026` tests.
- Legacy workflow artifact-root assertions and Windows subprocess/PATH failures.
- Stale committed evidence, Palace AMR report, and plugin bundle drift checks.

No failure is counted as a Palace execution result.

## Baseline quality gates

```text
$ .venv/Scripts/python.exe -m ruff check .
All checks passed!

$ .venv/Scripts/python.exe -m mypy src/textlayout
Success: no issues found in 151 source files

$ py -3 -m uv build
Building source distribution...
Building wheel from source distribution...
Successfully built dist\text_to_gds-0.3.0.tar.gz
Successfully built dist\text_to_gds-0.3.0-py3-none-any.whl
```

A fresh Python 3.12 virtual environment installed the built wheel with all
declared dependencies. `pip check` reported `No broken requirements found.`,
`import textlayout` succeeded, and `pip show text-to-gds` reported version
`0.3.0` from the clean environment.

## Solver and runtime capability

| Capability | Windows | WSL Ubuntu | Container |
| --- | --- | --- | --- |
| Gmsh executable | Not found | `/usr/bin/gmsh`, version 4.12.1 | Not probed without a Palace image |
| Gmsh Python module | Available in repository `.venv` | Not found in WSL system Python | Not applicable |
| Palace | Not found | Not found | No local Palace image found |
| MPI | Not found | Open MPI 4.1.6 (`mpiexec`, `mpirun`) | Image-dependent |
| Container engine | Docker CLI found | Not required | Docker Desktop 4.68.0, engine 29.3.1, daemon healthy |
| Podman | Not found | Not found | Not available |

No Palace executable exists in `.tools`. Docker is usable, but availability of
the engine alone is not Palace availability: no Palace image or digest was
present during this baseline.

## Baseline Palace verdict

`SKIPPED_SOLVER_ABSENT`

Palace was not invoked. No Palace-owned output was created or parsed, so this
baseline contains no Palace execution evidence.
