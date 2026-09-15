# Local benchmark validation

The 64-case grid checks analytical sizing and geometry without external solvers. Optional fresh FastHenry runs are reported separately below.

| Family | Cases | Geometry pass | Target pass (0.1%) | Worst target APE (%) |
| --- | ---: | ---: | ---: | ---: |
| CPW | 16 | 16 | 16 | 0.010368 |
| IDC | 16 | 16 | 16 | 0.000000 |
| QuarterWaveResonator | 16 | 16 | 16 | 0.000001 |
| SpiralInductor | 16 | 16 | 16 | 0.000000 |

## Published references (distinct devices and physics)

| Reference | Metric | Paper baseline | Tool | Delta | Status |
| --- | --- | --- | --- | --- | --- |
| [squadds](https://arxiv.org/html/2312.13483v3#S2.T1) | resonator frequency RMS error (%) | 3.8 | N/A | N/A | NOT_EVALUATED |
| [ye](https://arxiv.org/pdf/2511.09041) | maximum resonance APE (%) | <0.3 | N/A | N/A | NOT_EVALUATED |
| [sqdmetal_preprint](https://arxiv.org/html/2511.01220v2#S3.T1) | single resonator AMR frequency (GHz) | 9.993 | N/A | N/A | NOT_EVALUATED |

Fresh solver outputs on matching paper geometries are required for parity.
Failed cases remain in the population. Raw prompts, results, artifact hashes, dependency versions and source hash are in results.json.

## Published spiral-model reproduction

[Mohan Table IV](https://web.stanford.edu/~boyd/papers/pdf/inductance_expressions.pdf): 29/29 supported rows reproduce the printed modified-Wheeler error column within 0.5 percentage points (rounded coefficients/dimensions).

| Metric, identical 29-row subset | Paper model | This implementation |
| --- | ---: | ---: |
| RMS error against measurements (%) | 8.9787 | 8.9369 |
| Maximum deviation from printed model error (pp) | 0 | 0.2146 |

Worst measurement APE: 19.749%. This reproduces a published analytical model; it is not independent EM validation.

## Fresh FastHenry extraction

Executed 16/16 local spiral cases; 16/16 pass geometry and the 5% inductance target.

Local normal-metal quasi-static extraction, not paper-device parity; not a mesh-convergence study; no superconducting kinetic inductance

