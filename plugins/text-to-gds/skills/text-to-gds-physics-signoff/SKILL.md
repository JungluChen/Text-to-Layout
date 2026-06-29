---
name: text-to-gds-physics-signoff
description: Perform strict superconducting quantum EDA physics signoff. Use when a design needs Level 5+ evidence: extraction, real solver execution, independent solver agreement, review committee checks, and explicit rejection of fake or skipped solver evidence.
---

# Text-to-GDS Physics Signoff

## When To Use This Skill

Use this skill only when the user asks whether a layout is physically proven,
ready for research signoff, or acceptable as solver-backed quantum EDA output.

## Inputs

- `design_intent.json`
- `.gds`
- `.sidecar.json`
- `.drc.json`
- `.extraction.json`
- `physics_graph.json`
- Solver result files from at least two independent solvers.
- Optional measurement data for Level 6.

## Outputs

- Physics signoff report.
- Signoff Level 0-6.
- Solver agreement result.
- Review committee result.
- Blocking failures and repair actions.
- Executed/skipped/failed solver table.

## Required Files

- `SOLVER_EVIDENCE_CONTRACT.md`
- `PHYSICS_GRAPH_SCHEMA.md`
- `SIGNOFF_CRITERIA.md`
- `src/text_to_gds/signoff.py`
- `src/text_to_gds/review/`
- `src/text_to_gds/solver_agreement.py`

## Hard Stops

- Do not accept GDS as source of truth; use `physics_graph.json`.
- Do not count skipped solvers as evidence.
- Do not accept `source="LLM"` for physical values.
- Do not call Level 0-4 results `physics signoff`.
- Do not call results `measurement-calibrated` without imported measurement
  data and a fit.
- Reject CPW without ground-signal-ground evidence.
- Reject JPA without nonlinear Josephson junction model evidence.

## Solver Requirements

Physics signoff requires Level 5:

- One solver output is not enough.
- Two independent solver outputs must exist.
- Solver agreement must pass tolerance.
- Analytical estimates can support sanity checks but cannot replace solvers.

Measurement-calibrated status requires Level 6:

- Imported measurement file.
- Fit result.
- Clear comparison against simulation or extracted model.

## Example Prompts

- "Run physics signoff on this JPA artifact bundle."
- "Reject this CPW if openEMS did not produce a Touchstone file."
- "Tell me whether this can be called measurement-calibrated."

## Example Commands

```bash
uv run python scripts/check_external_tools.py
uv run python examples/zero_to_one_demos.py all
uv run pytest tests/test_signoff_contract.py
```

## Failure Cases

- Solver result has `status="executed"` but output file is missing.
- Two solvers ran but disagree beyond tolerance.
- Review committee has any blocking error.
- Measurement data is absent but report claims calibration.
