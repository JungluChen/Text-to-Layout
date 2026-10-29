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



### Windows QEDA identity diagnostic

Developer command: `uv run --no-sync python scripts/diagnose_qeda_capture_identity.py
--out out/qeda-identity/local.json`. Requires the development environment; output
must not exist. Creates and removes1000temporary regular-file trees, attempting
two unchanged captures each. Writes platform/Python/source hash, failure count
and up to20failure samples with named device/inode/size/mtime_ns/ctime_ns fields.
The identity wrapper returns original values unchanged. No solver/runtime
execution, network or capture acceptance decision is added. Status is
ANOMALY_OBSERVED or NOT_REPRODUCED; neither is installation/scientific acceptance.
Unexpected infrastructure errors fail the command. Existing output raises
FileExistsError; preserve it and choose a new output path.

Manual workflow `qeda-identity-diagnostic.yml` runs first/repeat on Windows
Python3.11/3.12 with15minute job limits and retained JSON artifacts. A green job
means collection completed, not that capture is fixed. Inspect failure_count and
identity_events, compare same source hashes, and retain both runs before editing.
AI prompt: “Compare the diagnostic metadata fields and identify observations
without inferring the cause from a green workflow.” No CLI product/MCP method,
GUI or screenshot is introduced. Entry008 remains pending.
