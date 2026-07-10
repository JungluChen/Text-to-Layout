# Evidence Labels

Use these exact labels. Store them as structured records with prerequisites, status, artifact paths, producer, backend/version where applicable, and failure or skip reason.

| Label | Minimum proof |
| --- | --- |
| `INTENT_PARSED` | Valid `intent.json` generated from the source request with explicit units and assumptions. |
| `DESIGN_SIZED_ANALYTICALLY` | Reproducible `design_equations.json` containing inputs, equations, results, and limitations. |
| `LAYOUT_DSL_GENERATED` | Valid typed Layout DSL in `layout.json`; no freehand AI polygon path. |
| `LAYOUT_GENERATED` | Deterministic generator produced non-empty GDS and preview artifacts from the recorded DSL. |
| `LAYOUT_VERIFIED` | Required geometry/connectivity/rule checks passed and GDS readback is recorded in `verification.json`. |
| `EXTRACTION_INPUT_PREPARED` | Geometry-derived electrostatic/EM input packet exists with units, materials, nets, source-layout hash, and command. |
| `EXTRACTION_EXECUTED` | A real extraction subprocess completed and retained logs plus non-empty solver-owned output. |
| `CAPACITANCE_EXTRACTED` | A real extraction output was parsed with units, conductor mapping, provenance, and validity checks. |
| `JOSIM_INPUT_PREPARED` | A JoSIM deck and run manifest exist; JoSIM has not necessarily run. |
| `JOSIM_EXECUTED` | A real JoSIM process completed and retained logs plus non-empty output. |
| `JOSIM_TRANSIENT_PARSED` | A real JoSIM output file was parsed and validated. |
| `JOSIM_RESONANCE_CHECKED` | Resonance was derived from parsed JoSIM data with method, target, tolerance, and pass/fail. |
| `PSCAN2_INPUT_PREPARED` | A PSCAN2 deck/project and run manifest exist; PSCAN2 has not necessarily run. |
| `PSCAN2_EXECUTED` | A real PSCAN2 process completed and retained logs plus non-empty output. |
| `PSCAN2_TRANSIENT_PARSED` | A real PSCAN2 output file was parsed and validated. |
| `PSCAN2_RESONANCE_CHECKED` | Resonance was derived from parsed PSCAN2 data with method, target, tolerance, and pass/fail. |
| `WRSPICE_INPUT_PREPARED` | A WRspice deck and run manifest exist; WRspice has not necessarily run. |
| `WRSPICE_EXECUTED` | A real WRspice process completed and retained logs plus non-empty output. |
| `WRSPICE_TRANSIENT_PARSED` | A real WRspice output file was parsed and validated. |
| `WRSPICE_RESONANCE_CHECKED` | Resonance was derived from parsed WRspice data with method, target, tolerance, and pass/fail. |
| `GAIN_CHECKED` | Pump, signal, and idler data from real parsed circuit-simulator output support a declared gain metric and tolerance check. |
| `PHYSICS_VERIFIED` | Layout is verified, geometry-level capacitance extraction passes its declared tolerance, and at least one real circuit simulation passes all declared circuit tolerances; requested gain also requires `GAIN_CHECKED`. |
| `SKIPPED_SOLVER_ABSENT` | An optional solver was unavailable; include backend, discovery method, reason, and valid prepared inputs if present. |
| `FAILED` | A required gate or attempted operation failed; include stage, reason, diagnostics, and retained logs/artifacts. |

## Enforcement Rules

- Input prepared is not execution.
- Execution requires a real subprocess or simulator call, captured command/version/return code, and a non-empty solver-owned output artifact.
- Parsed requires a real output file and successful schema/unit validation.
- A checked label requires a parsed result, declared target, declared tolerance, comparison method, and pass/fail result.
- `GAIN_CHECKED` requires pump, signal, and idler data. A passive resonance response is insufficient.
- `PHYSICS_VERIFIED` requires declared tolerance passes for both geometry-level extraction and circuit simulation.
- JoSIM, PSCAN2, and WRspice values assigned in a deck are circuit inputs, not extracted IDC capacitance.
- `SKIPPED_SOLVER_ABSENT` never satisfies an executed, parsed, checked, or verified prerequisite.
- `FAILED` never promotes evidence. Preserve earlier valid labels, but identify which downstream claims are invalidated.
- Any changed layout or material stack invalidates extraction and all circuit results derived from it.
