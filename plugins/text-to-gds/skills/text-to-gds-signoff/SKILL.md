---
name: text-to-gds-signoff
description: Audit Text-to-GDS artifacts for local release readiness, signoff level, DRC, extraction, solver evidence, measurement evidence, documentation claims, and remaining risks.
---

# Text-to-GDS Signoff

## When To Use This Skill

Use this skill when the user asks whether a layout, benchmark, report, demo, or
release is trustworthy.

## Inputs

- GDS path.
- Sidecar path.
- DRC report.
- Extraction and physics graph reports.
- Solver result records.
- Optional measurement data and fit reports.

## Outputs

- Signoff Level 0-6.
- PASS/FAIL verdict.
- Blocking failures.
- Executed and skipped solver lists.
- Required manual install steps.
- Remaining limitations.

## Required Files

- `src/text_to_gds/signoff.py`
- `SOLVER_EVIDENCE_CONTRACT.md`
- `SIGNOFF_CRITERIA.md`
- `scripts/check_external_tools.py`

## Hard Stops

- Level 5+ is required for `physics signoff`.
- Level 6 is required for `measurement-calibrated`.
- Missing sidecar blocks extraction.
- Missing solver output file invalidates `executed`.
- Skipped solvers never count as evidence.

## Solver Requirements

At least one real solver output is required for Level 4. Two independent solver
outputs plus agreement are required for Level 5.

## Example Prompts

- "Audit these artifacts and tell me the signoff level."
- "Can this benchmark claim physics signoff?"
- "List solvers executed, skipped, and missing install steps."

## Example Commands

```bash
uv run python scripts/check_external_tools.py
uv run python examples/zero_to_one_demos.py all
uv run pytest tests/test_signoff_contract.py
```

## Failure Cases

- Report claims simulation without output files.
- Analytical estimate is mislabeled as simulation.
- Measurement-calibrated label is used without imported measurement data.
