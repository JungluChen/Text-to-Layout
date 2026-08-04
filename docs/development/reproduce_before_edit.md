# Reproduce before edit

**Document status:** `MANUAL_DOCUMENTATION` — canonical repository policy.

This policy is mandatory for humans and coding agents working in this
repository. It applies whenever a test, simulation, solver, installation,
build, platform check, benchmark, CLI command, or API command fails or produces
an unexpected result.

## Required diagnostic sequence

```text
REPRODUCE
RERUN UNCHANGED
DIAGNOSE
EDIT
RERUN ORIGINAL COMMAND
RERUN AGAIN
REGRESSION
COMMIT
```

Never use `FAIL → GUESS → EDIT`.

Before changing a tracked file in response to a failure:

1. Save the exact command, exit code, complete stdout/stderr, runtime, working
   directory, git SHA, OS, architecture, Python and dependency versions,
   relevant environment variables, solver identity/version/path/SHA-256,
   random seed, input hashes, and output hashes where applicable.
2. Run the exact command again without changing tracked source, configuration,
   expected values, thresholds, or fixtures.
3. Compare exit status, diagnostics, numeric values, artifacts, hashes,
   convergence history, and runtime.
4. If the two runs disagree, **STOP EDITING**. Investigate nondeterminism,
   external state, concurrency, caches, environment, or insufficiently fixed
   inputs first. Use a third unchanged run when useful.
5. Diagnose a code defect only after it reproduces or independent evidence
   proves it. A single failure is not proof of a defect; a single pass is not
   proof of a fix.
6. Make the smallest change that addresses the diagnosed cause. Do not weaken
   scientific acceptance criteria or replace invalid numerical evidence with an
   analytical estimate.
7. Run the original command again, then run it one more time without editing.
8. Add or update a regression test that fails for the reproduced cause and
   passes for the fix.
9. Run proportionate surrounding gates, inspect the diff, and commit a focused
   change with the reproduction and verification evidence available for review.

## Environment-blocked failures

If the required environment cannot be executed—such as WSL2 from a macOS-only
host—do not change platform-specific product behavior based on speculation and
do not claim certification. Prepare deterministic collection infrastructure,
record the state as blocked or untested, and provide the exact command and
required evidence for the real host.

## Expensive solver failures

First reproduce the smallest faithful deterministic case, then rerun the full
benchmark before accepting a fix. Retain solver-owned inputs, outputs, logs,
identity, convergence, and resource-limit evidence. Installation, discovery,
input preparation, process exit, output parsing, convergence, independent
validation, and measurement correlation remain distinct states.

