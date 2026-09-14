# Requirements to a reviewable chip layout

This repository supplies deterministic design tools an AI assistant can call.
An assistant can be local or hosted; this package requires neither a hosted
model nor a commercial EDA license. It supports a bounded set of microwave and
superconducting component families, not arbitrary electronic or architectural
layout. The natural-language parser is a rules engine, not a trained LLM.

## A useful request

State the device, physical target, operating conditions, and manufacturing
constraints. For example:

> Create a 50 ohm CPW on silicon at 6 GHz with 8 um min gap.

Run `uv run python demo.py --prompt "..." --out out/design --no-solver`.
An AI caller should inspect `intent.json` and `design_review.json` to verify
that every requested condition was represented. Unsupported constraints need
explicit implementation or a supported typed DSL/PDK; they must not be treated
as satisfied merely because the parser extracted other parts of a sentence.

The review explains why the dimensions were selected. For CPW, the lossless
quasi-static model sets impedance through an elliptic-integral function of the
gap/width ratio. SciPy finds that ratio; both dimensions are then scaled to
honor minimum width/gap and the export grid. A fabrication constraint should
not erase the electrical target.

For IDC, integer fingers provide coarse tuning and overlap provides fine
tuning. For a spiral, the modified-Wheeler expression supplies an initial
size; real FastHenry extraction can trigger bounded retuning. A quarter-wave
resonator starts from electrical length and still needs a field solver for
loaded resonance and coupling.

## Review roles and accumulated experience

`design_review.json` contains engineering rules from
`src/textlayout/research/design_rules.py`, together with the existing cited
research report. The rules cover process assumptions, microwave models,
geometry/connectivity, physical extraction and measurement correlation. They
are inspectable knowledge, not claims that an AI model has been trained or
that an expert committee has approved a design.

The AI caller should use the artifact chain in order:

1. **Requirements:** compare the typed intent with the request, including units
   and every constraint. Reject or clarify an unsupported condition.
2. **Geometry:** require successful verification and independent GDS readback.
   Inspect `output.png`/`output.svg` and retain `output.gds`.
3. **Physics:** inspect solver execution, raw output, extraction and target
   error. `--require-simulation` prevents a missing solver from satisfying the
   demonstration's physical target gate. That gate is not mesh convergence or
   measurement validation.
4. **Measurement:** pair predictions with measurements of the same design and
   process, then assess corrections on held-out devices.

Existing process-learning commands are available:

```bash
textlayout measurement compare --help
textlayout measurement calibrate --help
textlayout pdk apply-calibration --help
```

Calibration records carry design/PDK hashes and a synthetic-data flag. Supply
real measured device records before claiming process learning; do not turn
generated layouts, the local solver sweep, or historical paper devices from
different processes into a fabrication calibration. Retain unfitted devices
to test generalization and preserve the uncalibrated result for comparison.

## Calling from an AI application

The simplest interface is the CLI above. The existing local HTTP service also
accepts `POST /layout/from-text` with a JSON body containing `prompt`,
`execute_solver`, and `tolerance_percent`; use `textlayout serve --help` to
configure it. The response includes intent, verification, evidence and file
paths. Keep the service local unless access controls have been configured.
For detailed geometry, use the supported `LayoutSpec`/`GenerateWorkflow` API.
The legacy MCP package remains frozen; new integrations should use `textlayout`.

## What remains to replace a commercial verification flow

Recent-paper parity needs matched device geometry, stack, boundary conditions,
ports and a converged open-source field-solver run. This audit reproduces
Mohan's analytical table and performs actual normal-metal FastHenry extraction.
It does not reproduce SQuADDS/PalaceForCQED device measurements, validate
superconducting kinetic inductance, qualify a foundry PDK, or demonstrate
arbitrary circuit placement/routing. Those are separate acceptance tests;
their absence remains visible in the benchmark and design review.
