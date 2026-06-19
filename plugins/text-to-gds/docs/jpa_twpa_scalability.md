# JPA/TWPA Scalability Architecture

## Real Problem

JPA and TWPA models must share artifact contracts without sharing invalid
physics. A lumped reflection JPA, a Josephson traveling-wave amplifier, a
kinetic-inductance TWPA, and a photonic-crystal SQUID chain require different
state variables and solvers. Treating them as one generic gain surrogate makes
optimization fast but scientifically weak.

The scalable boundary is therefore:

1. typed device and process configuration;
2. reusable linear engines for layout-derived dispersion and matching;
3. replaceable nonlinear solver backends;
4. benchmark definitions with independent, calibrated, and unsupported outputs
   identified separately;
5. stable JSON/CSV/plot artifacts for optimization and regression tests.

## Evidence From The Bundled Papers

| Paper | Design fact used by the project | Verification |
| --- | --- | --- |
| `PhysRevX.10.021021.pdf` | A 2160/2184-SQUID photonic crystal uses periodic junction and ground-capacitance modulation. | Discrete periodic LC eigenproblem reproduces the sample A/B gap centers within 1%. |
| `1612.00365v2.pdf` | Periodically loaded KIT behavior follows from its Floquet band structure. | Piecewise transmission-line matrices reproduce the first nine reported stop-gap edges within 0.7% and widths within 4.5%. |
| `2209.11052v2.pdf` | A 1500-cell rf-SQUID JTWPA with a 20-cell capacitance profile suppresses the pump second harmonic and supports 3-9 GHz gain. | Appendix-B ABCD matrices independently reproduce both stop bands and a 2401-cell coherence length versus 2186 reported; reduced gain remains above 19 dB from 3-9 GHz. |

## Implemented Scaling Contract

`Jtwpa3WMConfig` contains the line length, loading period, complete capacitance
profile, SQUID inductance, junction capacitance, reference impedance, pump, and
sweep definition. The solver accepts any valid configuration rather than
branching on a paper name.

The linear solver works on all frequency points simultaneously. One loading
period costs `m` ABCD multiplications and the repeated line uses binary matrix
exponentiation. For `F` frequencies, `m` cells per period, and `N` total cells,
the complexity is:

```text
time:   O(F * (m + log(N/m)))
memory: O(F)
```

This permits large parameter sweeps without constructing or multiplying 1500
Python matrix objects for every frequency.

Every paper benchmark emits:

- typed input configuration;
- independently calculated quantities;
- declared paper-calibrated quantities;
- explicit unsupported physics;
- numerical checks and pass/fail status;
- JSON, CSV, and PNG evidence.

## Next Solver Backends

The configuration and artifact contracts are ready for stronger nonlinear
engines. They should be added in this order:

1. Multi-tone coupled-mode integration with pump depletion and configurable
   generated tones.
2. JosephsonCircuits.jl/WRspice execution using the same configuration and
   output schema.
3. Loss, fabrication disorder, finite-loop inductance, and reflection-aware
   Monte Carlo sweeps.
4. External-simulator objectives in Optuna, with caching keyed by configuration
   hash and simulator version.
5. Parallel design-space execution with deterministic seeds and bounded worker
   counts.

The reduced gain models must not be relabeled as signoff models. A benchmark
passes only the checks listed in its JSON; it does not imply noise,
compression, fabrication-yield, or foundry signoff.
