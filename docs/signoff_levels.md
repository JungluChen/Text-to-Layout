# Signoff levels — `textlayout.signoff`

Signoff is sequential and evidence-gated. A quantity can be
`PHYSICS_VERIFIED` when one solver converges and meets its target, but the
design reaches Level 5 only when two independent solver families agree about
the same design hash, analysis scope, and quantity.

## The seven levels

<!-- SIGNOFF_LEVEL_TABLE_BEGIN -->
| Level | Label | Requires |
| ---: | --- | --- |
| -1 | No geometry | Geometry was not generated or failed verification. |
| 0 | Geometry generated | GDS exists and passed layout verification. |
| 1 | DRC passed | Level 0 plus the design-rule check passed. |
| 2 | Extraction complete | Level 1 plus extraction/readback completed. |
| 3 | Analytical sanity | Level 2 plus analytical sanity checks. |
| 4 | One solver executed | Level 3 plus one valid solver-backed canonical record, or the temporary single-record `evidence=` compatibility input. |
| 5 | **Physics signoff** | Level 4 plus at least two canonical `PHYSICS_VERIFIED` records from independent solver families (distinct backends) and a passing computed agreement record for the same design hash, analysis scope, and quantity. |
| 6 | **Measurement-calibrated** | Level 5 plus a `CalibrationFile` with `synthetic=False`. |
<!-- SIGNOFF_LEVEL_TABLE_END -->

The result schema is `textlayout.signoff.v2`. It reports executed solver IDs
(the canonical evidence IDs), normalized solver families, computed agreement
status, explicit blockers, and the existing Level 5/6 compatibility booleans.

## Usage

```python
from textlayout.evidence import SolverAgreementRecord, load_canonical
from textlayout.signoff import evaluate_signoff

openems = load_canonical("openems_evidence.json")
palace = load_canonical("palace_evidence.json")
agreement = SolverAgreementRecord.model_validate_json(
    open("solver_agreement.json", encoding="utf-8").read()
)

result = evaluate_signoff(
    geometry_pass=True,
    drc_passed=True,
    verification_passed=True,
    solver_evidence=[openems, palace],
    solver_agreement=agreement,
    calibration=calibration_file,
)
print(result.level, result.executed_solver_families, result.blockers)
```

The older `evidence=QuantityEvidence(...)` argument remains accepted during the
compatibility window, but it can reach only Level 4. Passing a real calibration
beside one solver cannot skip the independent-agreement gate.

Agreement is computed from converted values and cannot be supplied by the
caller. Every member identifies a canonical evidence ID, normalized solver
family, finite extracted value and unit, and at least one non-empty SHA-256
addressed solver output. Unsupported or dimensionally incompatible units fail
closed.
