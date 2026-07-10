# The evidence model

Every physics claim in this repository is a `QuantityEvidence` record. The model
does not *document* the honesty rules — it **enforces** them in a pydantic
validator, so a false claim cannot be constructed at all.

Source: [`src/textlayout/evidence.py`](../src/textlayout/evidence.py).

## The one invariant

> Confidence may always be **lost**, and may only be **gained** along the
> sanctioned path: prepare inputs → run a solver → compare to target.

Losing confidence is always honest — a re-run that fails must always be able to
invalidate an earlier claim. So demotion needs no allow-list. Only the
confidence-*increasing* edges are enumerated, and everything else that would
raise confidence is an illegal promotion.

## Statuses and confidence classes

| Status | Confidence | Means |
| --- | --- | --- |
| `FAILED` | `NONE` | Solver ran, produced no accepted result. |
| `SKIPPED_SOLVER_ABSENT` | `NONE` | Solver not installed. **An honest skip, not a failure.** |
| `SIMULATION_INVALID` | `NONE` | Solver ran; output failed a physical-sanity check. |
| `CONVERGENCE_FAILED` | `NONE` | Solver ran; result did not converge under refinement. |
| `ANALYTICAL_ONLY` | `ANALYTICAL` | Closed-form estimate. **Never a solver result.** |
| `SIMULATION_INPUT_PREPARED` | `PREPARED` | Solver inputs exist on disk. Still not a result. |
| `SIMULATION_EXECUTED` | `SIMULATED` | Solver produced a finite, parseable value. |
| `PHYSICS_VERIFIED` | `VERIFIED` | That value agreed with its target inside tolerance. |

`ConfidenceClass` is an `IntEnum`, so "did this transition raise confidence?" is
a comparison rather than a hand-maintained table of forbidden pairs.

## The lattice

```mermaid
stateDiagram-v2
    direction LR
    [*] --> ANALYTICAL_ONLY
    [*] --> SKIPPED_SOLVER_ABSENT

    ANALYTICAL_ONLY --> SIMULATION_INPUT_PREPARED
    SKIPPED_SOLVER_ABSENT --> SIMULATION_INPUT_PREPARED
    SIMULATION_INVALID --> SIMULATION_INPUT_PREPARED
    CONVERGENCE_FAILED --> SIMULATION_INPUT_PREPARED
    FAILED --> SIMULATION_INPUT_PREPARED

    SIMULATION_INPUT_PREPARED --> SIMULATION_EXECUTED
    SIMULATION_EXECUTED --> PHYSICS_VERIFIED

    SIMULATION_EXECUTED --> SIMULATION_INVALID
    SIMULATION_EXECUTED --> CONVERGENCE_FAILED
    PHYSICS_VERIFIED --> SIMULATION_INVALID : re-run invalidates
    PHYSICS_VERIFIED --> SKIPPED_SOLVER_ABSENT : solver disappeared

    note right of PHYSICS_VERIFIED
        The ONLY edge into PHYSICS_VERIFIED
        starts at SIMULATION_EXECUTED.
    end note
```

Solid arrows upward are the 11 sanctioned promotions. Every downward edge is
permitted implicitly and is not enumerated.

## Structural guards

Constructing a record runs these checks, in this order:

1. **Non-finite rejection.** No numeric field may be `NaN` or `±inf`.
   This runs *first*, because `NaN` compares `False` against every bound: an
   unguarded `error_percent > tolerance_percent` check silently **admits** a
   `NaN` error as `PHYSICS_VERIFIED`. That was a real defect — see
   [`improvement_baseline.md`](improvement_baseline.md).
2. **Rejected statuses** (`SIMULATION_INVALID`, `CONVERGENCE_FAILED`) must name
   a solver and must **not** carry an extracted value. A rejected number is not
   a measurement of anything; the raw token is preserved in `notes`.
3. **Solver-output statuses** (`SIMULATION_EXECUTED`, `PHYSICS_VERIFIED`) require
   a named solver, a named parser, an extracted value, and at least one output
   file that **exists and is non-empty on disk**.
4. **`PHYSICS_VERIFIED`** additionally requires a target and an `error_percent`
   within `tolerance_percent`.
5. **`ANALYTICAL_ONLY`** must not name a solver or claim solver output files.
6. **`SKIPPED_SOLVER_ABSENT` / `SIMULATION_INPUT_PREPARED`** must not carry an
   extracted value: no solver ran, so there is nothing to extract.

`compare_extracted_to_target()` is the only path to `PHYSICS_VERIFIED`. It
*computes* the status and never accepts one:

- non-finite extracted value → `SIMULATION_INVALID`
- inside tolerance → `PHYSICS_VERIFIED`
- outside tolerance → `SIMULATION_EXECUTED`

## The ledger

`EvidenceLedger` is an append-only history of one quantity's claims. `record()`
validates each transition against the lattice; `from_dict()` re-validates the
**whole chain**, so a ledger file hand-edited to promote a claim will not load.

```python
from textlayout.evidence import EvidenceLedger, EvidenceStatus

ledger = EvidenceLedger("capacitance")
ledger.record(prepared)    # SIMULATION_INPUT_PREPARED
ledger.record(executed)    # SIMULATION_EXECUTED   -> ok
ledger.record(verified)    # PHYSICS_VERIFIED      -> ok

ledger.current.confidence_class   # ConfidenceClass.VERIFIED
```

Attempting to skip the solver:

```python
ledger = EvidenceLedger("capacitance")
ledger.record(skipped)     # SKIPPED_SOLVER_ABSENT
ledger.record(verified)    # EvidenceError: illegal confidence promotion
                           # SKIPPED_SOLVER_ABSENT -> PHYSICS_VERIFIED
```

## Validating stored evidence in CI

```bash
uv run textlayout evidence check path/to/ledger.json
```

| Exit | Meaning |
| --- | --- |
| `0` | Schema valid; every recorded transition is legal. |
| `3` | Schema invalid, or a claim was promoted illegally. |

Schema id: `textlayout.evidence-ledger.v1`.

## Reproducing the tests

```bash
uv run pytest tests/textlayout_suite/test_evidence_transitions.py   # 83 tests
uv run pytest tests/textlayout_suite/test_evidence_contract.py      # 18 tests
```

`test_evidence_transitions.py` sweeps all 8 × 8 = 64 status pairs against an
**independently restated** promotion set, so widening the lattice in
`evidence.py` alone fails the suite — the graph must be changed deliberately in
two places.

## What this model does *not* claim

A `PHYSICS_VERIFIED` quantity means one solver agreed with one target inside
tolerance. It does **not** mean the design is fabrication-ready. Nothing is
fabrication-ready without a process-qualified PDK and all required signoff
checks. See [`pdk_abstraction.md`](pdk_abstraction.md).

---

# Canonical evidence (schema v2) and the derivation graph

Everything above describes the per-quantity honesty contract. It was not
enough: statuses were *strings copied into each artifact at generation time*.
A resonator openEMS run produced an all-NaN Touchstone, its low-level result
was corrected to `SIMULATION_INVALID`, and eight derived artifacts kept
publishing a successfully extracted 3.0 GHz resonance. See
[`evidence_consistency_baseline.md`](evidence_consistency_baseline.md).

`CanonicalEvidence` (`textlayout.canonical-evidence.v2`) is now the only source
of truth. Every public artifact is a projection of it.

```mermaid
flowchart TD
    O[committed solver output<br/>.s2p / stdout / Zc.mat] --> B[build_canonical]
    B -->|re-parse, recompute,<br/>read back convergence| C[(evidence/canonical.json)]
    C --> S1[simulation.json<br/>+ embedded evidence#91;#93;]
    C --> S2[simulation/simulation.json]
    C --> S3[openems_result.json<br/>extraction/capacitance_result.json]
    C --> T[workflow_trace.json<br/>stamped, never rewritten]
    C --> R1[report.md<br/>GENERATED block]
    C --> R2[showcase README.md<br/>GENERATED block]
    C --> I[examples/showcase/index.json]
    C --> R3[README.md<br/>5 GENERATED blocks]
```

## Status is computed, never asserted

`build_canonical` trusts no status string. It re-parses the committed solver
output with the current parser and computes:

| Condition | Status |
| --- | --- |
| parser rejects the output | `SIMULATION_INVALID` |
| no convergence criterion evidenced | `SIMULATION_EXECUTED` |
| converged and inside tolerance | `PHYSICS_VERIFIED` |
| converged and outside tolerance | `SIMULATION_EXECUTED` |

No solver is re-run and no evidence is fabricated. Convergence is *read back
from what the solver did*, never asserted:

- **FasterCap** — `-a0.01` automatic panel refinement to 1%, taken from the
  recorded command.
- **openEMS** — the field-energy-decay and excitation-support gate. A genuine
  time-domain convergence criterion; **not** a mesh-refinement study, and the
  record says so.
- **FastHenry** — the deck declares no `nhinc`/`nwinc` and there is no
  refinement sweep, so **no convergence is claimed** and the spiral cannot be
  `PHYSICS_VERIFIED`.

## Provenance: a path is not evidence

Every input and output file is a SHA-256 content hash.
`verify_output_hashes()` re-hashes them, so a solver output edited after its
evidence was written is detected — the failure a path-existence check cannot
see. The extraction configuration is hashed too, because the same parser over
the same Touchstone yields 49.712535 Ω at the design frequency and 49.714711 Ω
at the sweep centre.

`git_commit` records the commit that last changed *this record's own files*,
not `HEAD`. Recording `HEAD` would make every record stale on any unrelated
commit.

A solver-backed record with no executable hash or container digest must declare
`solver_executable_hash_unrecorded` in `provenance_gaps` rather than pretend
its provenance is complete. All five historical solver runs carry that gap.

## Generated blocks

Markdown carries `<!-- BEGIN GENERATED: <name> --> ... <!-- END GENERATED -->`.
Only text inside a block is authoritative; a document with no block is reported
as unverifiable rather than assumed correct. The block replaces the *whole*
status region, so stale prose cannot survive beside it.

`workflow_trace.json` is the exception: it records what each node observed when
the workflow ran. Rewriting it would falsify the record. It is *stamped* with
`canonical_evidence_status`, and the status that run reported is preserved as
`run_reported_status` with a `historical_note`.

## Withdrawn claims

A `SIMULATION_INVALID` record carries **no** extracted value. The withdrawn
number lives only in `superseded`, with the reason:

```json
"superseded": {
  "status": "RESONANCE_FREQUENCY_EXTRACTED",
  "extracted_value": 3.0, "extracted_unit": "GHz",
  "why_withdrawn": "3.0 GHz is the first point of the sweep, not a resonance..."
}
```

## CI gates

```bash
uv run python scripts/build_canonical_evidence.py --check   # record re-derives
uv run python scripts/render_showcase_artifacts.py --check  # nothing stale
uv run python scripts/audit_evidence_consistency.py         # nothing contradicts
```

The audit traverses `examples/showcase/` — never a hard-coded list — so a new
showcase is covered the day it is added.
