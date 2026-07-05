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

## Backends and honesty

| Backend | Status reported | What it is |
| --- | --- | --- |
| `analytical_surface_scaling` | `ANALYTICAL_ONLY` | Documented order-of-magnitude scaling model (below). Always available; used in CI. |
| `pyepr` | `SKIPPED_SOLVER_ABSENT` unless pyEPR + an HFSS eigenmode project exist | Field-solved participation extraction slot. Never fabricates numbers. |

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
`confidence = 0.3` and the result is `ANALYTICAL_ONLY`. The channel **ranking**
is more trustworthy than the absolute T1 number. Use it to compare design
variants and identify the dominant loss channel — not to promise coherence.

### The materials database

`illustrative_silicon_db()` ships order-of-magnitude loss tangents for
substrate bulk, metal–substrate, metal–air, substrate–air, and a junction
dielectric placeholder. **Every default is marked
`illustrative_literature_range` — none is foundry-calibrated.** A process can
provide its own `MaterialsDB` with `calibration: measured_on_process`; the
math is unchanged. Replacing illustrative values with measured ones is the job
of the measurement-calibration loop.

## Usage

```bash
# Standalone EPR / coherence report for a DSL file
textlayout epr examples/benchmarks/01_idc_0p6pf/layout.json --out out/evidence

# Append EPR to a verification run
textlayout verify examples/benchmarks/01_idc_0p6pf/layout.json --include-epr
```

Outputs: `out/evidence/epr_report.json` and `out/evidence/epr_report.md`,
each carrying backend, materials-DB id, assumptions, timestamp, and status.

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
- Absolute T1 numbers from `ANALYTICAL_ONLY` results must never be quoted as
  predictions. The status field enforces the vocabulary; keep it visible in
  any downstream report.
