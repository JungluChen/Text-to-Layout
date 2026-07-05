# EPR loss participation and coherence estimation

**Why this exists:** hitting a capacitance or impedance target says nothing
about whether a structure will make a good qubit or resonator. Coherence
(T1/T2) in superconducting circuits is dominated by *where the electric field
energy lives* — the energy participation ratio (EPR) of lossy dielectrics and
interfaces — not by the lumped C or Z0 value. A design flow that verifies
0.6 pF to 0.2% and ignores surface participation is answering the wrong
question for cQED. **Capacitance accuracy does not imply coherence accuracy.**

## What it computes

For each loss channel *i* with participation *p_i* and loss tangent *tanδ_i*:

```
1 / Q_total = Σ_i  p_i · tanδ_i
T1          = Q_total / ω = Q_total / (2π f)
```

The report includes per-channel Q/T1 limits, the dominant loss channel, a
sensitivity ranking (loss fraction per channel), and a "what to improve first"
recommendation.

## Status vocabulary

EPR uses its own five-value vocabulary (distinct from the shared
project-wide one) because a real EPR workflow has more real intermediate
states than a plain solver run:

| Status | Meaning |
| --- | --- |
| `EPR_INPUT_PREPARED` | Geometry/mesh input for a real extraction was generated; no participation computed yet. |
| `FIELD_ENERGY_IMPORTED` | A real, solver-exported field-energy file was parsed and participations computed from it — real solver-derived evidence, even though this project did not run the eigenmode solve itself. |
| `EPR_ANALYTICAL_ONLY` | Participations come from the scaling model below, never a field solution. |
| `EPR_EXECUTED` | This project ran a real EPR extraction end to end and parsed its output directly. |
| `EPR_SKIPPED_SOLVER_ABSENT` | The requested EPR solver stack is not installed; nothing is claimed. |

## Backends

| Backend | Status reported | What it is |
| --- | --- | --- |
| `analytical_surface_scaling` | `EPR_ANALYTICAL_ONLY` | Documented order-of-magnitude scaling model (below). Always available; used in CI. |
| `field_energy_import` | `FIELD_ENERGY_IMPORTED` (or `EPR_SKIPPED_SOLVER_ABSENT` if the export file is missing) | Parses an already-exported field-energy JSON (the same per-region electric-energy numbers a real pyEPR run produces) and combines it with materials-DB loss tangents. CI-safe: no HFSS or pyEPR needed. See "Field-energy import" below. |
| `pyepr` | `EPR_SKIPPED_SOLVER_ABSENT` unless pyEPR + an HFSS eigenmode project exist | Live field-solved participation extraction slot — interface only, not implemented. Never fabricates numbers. See [pyepr_hfss_integration.md](pyepr_hfss_integration.md) for the contract a real implementation must meet (and why `field_energy_import` above is usually the faster path). |

### The analytical scaling model

- Bulk substrate participation: `p_bulk ≈ ε_r / (ε_r + 1)` (≈0.92 for Si).
- Total thin-film surface participation scaled from a published reference
  point: `p_surf(g) = 3×10⁻³ × (2 µm / g)` where `g` is the smallest
  field-defining gap (order of magnitude from Wenner et al., APL 99, 113513
  (2011) for few-µm-gap CPW).
- MS : SA : MA split fixed at 4 : 3 : 2 (literature ordering), each scaled by
  interface thickness relative to 3 nm.
- Junction dielectric participation is **not** modelled.

This is a *scaling model*, not a field solution. Participations carry
`confidence = 0.3` and the result is `EPR_ANALYTICAL_ONLY`. The channel
**ranking** is more trustworthy than the absolute T1 number. Use it to compare
design variants and identify the dominant loss channel — not to promise
coherence.

### Field-energy import (CI-safe, real-data-shaped)

`FieldEnergyImportBackend` computes participations from an already-exported
field-energy file — the same per-region electric-energy-integral numbers a
real `pyEPR` run produces — without needing HFSS or pyEPR installed:

```python
from textlayout.epr import FieldEnergyImportBackend

backend = FieldEnergyImportBackend(
    "examples/epr_fixtures/field_energy_export_example.json"
)
result = backend.analyze(spec, frequency_ghz=6.0)  # status: FIELD_ENERGY_IMPORTED
```

The committed fixture (`examples/epr_fixtures/field_energy_export_example.json`)
is explicitly labelled synthetic in its own `source` field — shaped like a real
export so the parser and coherence math are tested against real-data
structure in CI, not claimed as a real measurement. Participations from this
backend carry `confidence=0.6` (higher than the analytical backend's `0.3`,
since they come from an actual field integral, not a formula) but the loss
tangents combined with them are still whatever the materials DB says —
illustrative unless that DB's `calibration` says otherwise.

### The materials database

`illustrative_silicon_db()` loads order-of-magnitude loss tangents from
`src/textlayout/knowledge/materials/illustrative_si_surface_loss.yaml` —
substrate bulk, metal–substrate, metal–air, substrate–air, and a junction
dielectric placeholder. **Every default is marked
`illustrative_literature_range` — none is foundry-calibrated.** A process can
ship its own YAML with the same schema (`load_materials_db(path)`) with
`calibration: measured_on_process`; the math is unchanged. Replacing
illustrative values with measured ones is the job of the
measurement-calibration loop.

## Usage

```bash
# Standalone EPR / coherence report for a DSL file
textlayout epr examples/benchmarks/01_idc_0p6pf/layout.json --out out/evidence

# Append EPR to a verification run
textlayout verify examples/benchmarks/01_idc_0p6pf/layout.json --include-epr

# Append EPR to the full natural-language design loop -- capacitance
# evidence AND EPR/coherence in one report.md, plus epr_report.json/.md
textlayout prompt "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap" \
  --out out/idc_demo --include-epr
```

Outputs: `out/evidence/epr_report.json` and `out/evidence/epr_report.md`,
each carrying backend, materials-DB id, assumptions, timestamp, and status.
With `textlayout prompt --include-epr`, the same content is additionally
folded into the design's own `report.md` as one nested section, so a single
report shows capacitance/inductance evidence next to EPR participation,
Q, T1, and the dominant loss channel. Without `--include-epr`, `report.md`
and the JSON payload are byte-for-byte unchanged — the flag is strictly
additive.

Python API:

```python
from textlayout.epr import default_epr_backend, write_epr_report

result = default_epr_backend().analyze(spec, frequency_ghz=6.0)
print(result.coherence.dominant_channel, result.coherence.t1_total_us)
write_epr_report(result, "out/evidence")
```

## Limits

- The analytical backend does not resolve geometry beyond the characteristic
  gap; two layouts with the same minimum gap get the same surface estimate.
- No magnetic participation, no packaging/seam loss, no TLS saturation, no
  quasiparticle loss.
- Absolute T1 numbers from `EPR_ANALYTICAL_ONLY` results must never be quoted
  as predictions. The status field enforces the vocabulary; keep it visible in
  any downstream report.
