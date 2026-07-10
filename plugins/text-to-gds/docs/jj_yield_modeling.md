# JJ critical-current variability and fabrication-yield modeling

**Why this exists:** drawing one SQUID loop that hits a target Ic/frequency
proves *geometry*, not *manufacturability*. Real fabrication has statistical
spread in Jc (critical current density) at two scales — wafer-to-wafer drift
and junction-to-junction local variation — plus lithography CD (critical
dimension) variation on the drawn junction area. All three propagate directly
into qubit-frequency spread through the exact relations:

```
Ic = Jc · A
LJ = Φ₀ / (2π · Ic)
f  = 1 / (2π √(LJ · C))
```

A single design that computes `f` from one nominal `(Jc, A)` pair answers "is
the formula right?" — not "will this chip work when I fabricate 1000 of
them?" That second question is what this module answers, with a seeded Monte
Carlo that propagates process statistics through the exact physics above into
a frequency distribution and a yield percentage.

## The process model

`JJProcessModel` separates variation into named, physically distinct sources:

| Parameter | What it represents |
| --- | --- |
| `wafer_jc_sigma_pct` | Chip-common Jc drift — every junction on one chip shares one draw. |
| `local_jc_sigma_pct` | Junction-to-junction local spread — independent per junction. |
| `cd_sigma_nm` | Lithography CD variation, applied additively to each drawn dimension. |
| `junction_area_bias_um2` | Systematic area bias (e.g. undercut). |
| `spatial_gradient_pct_per_mm` | Optional linear Jc gradient across a chip. |

**All defaults are `calibration="illustrative"` — not foundry-measured.** Feed
real process statistics (from `textlayout measurement calibrate`, see the
measurement-correlation loop) to get `calibration="measured_on_process"` and a
`synthetic=False` result.

## SQUID asymmetry

`squid_ic_eff_ua(Ic1, Ic2, Φ/Φ₀)` implements the standard asymmetric-SQUID
relation `Ic_eff(Φ) = (Ic1+Ic2)·√(cos²(πΦ/Φ₀) + d²sin²(πΦ/Φ₀))` with asymmetry
`d = |Ic1−Ic2|/(Ic1+Ic2)`. A **symmetric** SQUID biased at exactly half flux
has `Ic_eff → 0` and `LJ → ∞`; `squid_lj_nh` raises rather than returning a
divergent number, and `SquidGeometry` itself rejects that configuration at
construction time.

## Two analyses

### `textlayout yield jj` — single-junction/mode yield

Monte Carlo over one junction (or SQUID mode): reports the resulting
frequency distribution (mean, σ, p05/p50/p95, range), the fraction of samples
inside a `target_ghz ± tolerance_mhz` window (with a Wilson 95% confidence
interval — exact, not a normal approximation, so it stays valid near 0% or
100%), and the worst-case (min/max frequency) corners with the Jc/area/Ic/LJ
draw that produced them.

```bash
textlayout yield jj \
  --jc 1.0 --wafer-sigma-pct 5 --local-sigma-pct 3 \
  --width-um 0.1414 --height-um 0.1414 --shunt-c-pf 0.07 \
  --target-ghz 4.7 --tolerance-mhz 50 \
  --n-samples 5000 --seed 42 --out out/evidence
```

### `textlayout yield qubit-array` — chip-level yield

The practical question: if a chip needs **N** qubits *simultaneously* in
spec, what fraction of fabricated chips pass? Each simulated chip draws one
shared wafer-common Jc factor; each qubit within that chip then draws its own
local Jc, CD, and (optional) spatial-gradient contribution. A chip passes
only if every qubit lands inside the window.

```bash
textlayout yield qubit-array \
  --jc 1.0 --wafer-sigma-pct 5 --local-sigma-pct 3 \
  --width-um 0.1414 --height-um 0.1414 --shunt-c-pf 0.07 \
  --target-ghz 4.7 --tolerance-mhz 50 \
  --n-qubits 40 --n-chips 2000 --seed 42 --out out/evidence
```

**Why this matters — a real result from this exact example:** with 5% wafer +
3% local Jc sigma, a single junction's per-mode hit rate is ~29%. Naive
intuition might expect a 40-qubit chip to have a "somewhat lower" yield.
Instead, because each qubit's pass/fail is close to independent, the chip
yield collapses to **≈0%** — independent probabilities compound
multiplicatively (`0.29^40 ≈ 10⁻²²` order of magnitude, though correlated
wafer-common drift makes the real number less extreme than that naive
product). The report separates the per-junction hit-rate CI from the
chip-level yield CI so this distinction is never conflated.

**This is the core argument for why scaling superconducting qubit chips is a
*yield engineering* problem, not just a layout problem**: hitting a frequency
target on average is necessary but nowhere near sufficient once many qubits
must simultaneously succeed.

## Honesty and limits

- Every result carries `synthetic` (true unless `calibration="measured_on_process"`),
  the process source string, a seed for exact reproducibility, and the full
  list of modelling assumptions.
- Sampling is Gaussian only: no fat tails, no correlated defects (beyond the
  one shared wafer-common factor), no aging or thermal cycling effects.
- The chip-level Monte Carlo uses a synthetic linear qubit placement for the
  spatial gradient — real chip layouts should supply real coordinates.
- Confidence intervals use the exact Wilson score formula, valid even when
  the observed yield is exactly 0% or 100% (unlike a normal approximation).
