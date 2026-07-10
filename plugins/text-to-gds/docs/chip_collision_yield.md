# Multi-qubit chip-level frequency-collision analysis

**Why this exists:** a single-device closed loop — one IDC, one SQUID, one
resonator — cannot answer the question that determines whether a *processor*
works: once every qubit, coupler, and readout resonator on a chip has its own
process-driven frequency spread (see [JJ yield modeling](jj_yield_modeling.md)),
do any of them collide? A chip design is not "done" because each device hits
its target on average — it is done when the *whole lattice*, sampled across
realistic process variation, is collision-free with acceptable probability.

## The lattice model

`QubitLattice` is nodes (`QubitNode`: target frequency, optional own readout
frequency, anharmonicity, and a per-node frequency sigma — typically produced
upstream by `textlayout.yield_model`) plus edges (`CouplerEdge`: the
nearest-neighbor coupling graph, with an optional tunable-coupler mode
frequency). `CollisionRules` sets the minimum acceptable detuning for each
collision type.

## Collision taxonomy

| Rule | Check | Illustrative default |
| --- | --- | --- |
| `qubit_qubit` | Nearest-neighbor `|Δf|` too small — direct hybridization risk. | 30 MHz |
| `qubit_readout` | A qubit too close to its own readout resonator. | 500 MHz |
| `qubit_coupler` | A qubit too close to its (tunable) coupler mode. | 300 MHz |
| `two_photon` | `|Δf − |α||` too small — a two-photon exchange resonance hook. | 30 MHz |
| `charge_parity` | `|2Δf − |α||` too small — a next-order resonance hook. | 30 MHz |

**All default thresholds are illustrative order-of-magnitude values from the
published fixed-frequency-transmon frequency-crowding literature — not
calibrated to any specific device or foundry process.** Supply your own
`CollisionRules` once you have process-specific numbers.

Every check runs through one function, `evaluate_collisions`, so the
deterministic nominal report and every Monte Carlo sample use exactly the same
rule logic — there is no separate "fast path" that could silently diverge.

## Two analyses

### `textlayout chip analyze` — collision detection + Monte Carlo yield

1. **Nominal report**: are the target frequencies collision-free as designed?
2. **Monte Carlo yield**: sampling each node's frequency from
   `N(target_freq_ghz, freq_sigma_mhz)` (readout/coupler frequencies held
   fixed), what fraction of simulated chips are collision-free end to end,
   with a Wilson-exact 95% confidence interval?
3. **Risky pairs**: every (node pair, rule) ranked by how often it was the one
   that failed — the actionable output for a designer deciding where to widen
   margins.

```bash
textlayout chip analyze examples/chip_lattices/40_qubit_grid.json \
  --n-samples 2000 --seed 42 --out out/evidence
```

Writes `chip_yield_report.json`, `chip_yield_report.md`, and
`collision_matrix.csv` (one row per risky pair: node_a, node_b, rule,
collision_probability).

**A real result from the committed 40-qubit example:** a checkerboard
two-frequency-bin scheme (5.000 / 5.120 GHz, ±8 MHz process sigma) has 17
nominal violations and a Monte Carlo collision-free yield of **0.0%** — driven
almost entirely by `charge_parity` collisions, a next-order effect easy to
miss when only checking the primary qubit-qubit detuning by hand.

### `textlayout chip optimize` — greedy frequency-allocation retuning

Retunes the *frequency allocation plan* (which target each qubit is assigned
during design) to reduce or eliminate collisions, bounded by
`--max-retune-mhz` — representing the achievable Jc/frequency range a process
can actually hit. This is standard practice ("frequency binning") for
fixed-frequency transmon processors; it is not claiming a fabricated device
can be retuned after the fact.

```bash
textlayout chip optimize examples/chip_lattices/40_qubit_grid.json \
  --max-retune-mhz 50 --step-mhz 2 --out out/evidence
```

**On the same 40-qubit example**, a ±50 MHz retune budget resolves all 17
violations in 15 iterations (12 qubits retuned) — a modest, fabrication-
plausible adjustment.

**Why this needed a real bug fix during development:** an earlier version of
the optimizer used a binary violation *count* as its objective. A retuning
step that narrowed a violation from "10 MHz short of compliant" to "5 MHz
short" looked identical to "no improvement," so the search stalled instead of
converging. The objective is now the continuous total detuning *shortfall*
(MHz below each threshold, summed over all violations) — every step toward
compliance is visible, not just the one that finally crosses a threshold.

## Honesty and limits

- `synthetic=True` on every result; this is a modelling tool, not a
  measurement.
- The optimizer is a local greedy search, not a global optimum — it may
  converge without reaching collision-free, and it reports that honestly
  (`converged: false`).
- Readout and coupler frequencies are not resampled in the Monte Carlo and not
  retuned by the optimizer — only qubit target frequencies are.
- No correlated wafer-common factor is modeled here; if that matters, derive
  each node's `freq_sigma_mhz` including it upstream (e.g. from
  `textlayout.yield_model`) before building the lattice.
