# Benchmark specification

Document class: MANUAL_DOCUMENTATION. Sources checked 2026-09-13. This protocol
was written before the standardized sweep and its sizing changes.

## Domain and comparability

This project generates superconducting/microwave GDS geometry. Document-layout
datasets and visual overlap scores are inappropriate: intentional same-net metal
overlap connects conductors. Relevant tests are net shorts, conductor clearance,
GDS readback, impedance, resonance, and agreement with independent simulation or
measurement.

The following two peer-reviewed papers and one explicitly identified preprint
are relevant references. None provides a natural-language prompt benchmark for
this package. Their published device populations must not be replaced with
target-frequency prompts and called a replication. No SOTA ranking is claimed.

## 1. SQuADDS

Sadman Shanto, Andre Kuo, Clark Miyamoto, Haimeng Zhang, Vivek Maurya, Evangelos
Vlachos, Malida Hecht, Chung Wa Shum, Eli Levenson-Falk, **SQuADDS: A validated
design database and simulation workflow for superconducting qubit design**,
*Quantum* 8, 1465 (2024), DOI 10.22331/q-2024-09-09-1465.
[Paper and Table 1](https://arxiv.org/html/2312.13483v3#S2.T1).

Table 1 reports simulation-to-measurement RMS errors for six qubit/resonator
pairs: anharmonicity 4.1%, linewidth 16.9%, coupling 10.4%, resonance 3.8%.
The convergence setting is <0.05% between passes, with three converged passes.
Figure 1's measured resonance frequencies are 6.116, 6.353, 6.472, 6.568,
6.655, 6.704 GHz. Data: [SQuADDS database](https://huggingface.co/datasets/SQuADDS/SQuADDS_DB).
The original [WM1 design repository](https://github.com/LFL-Lab/design_schema_WM1)
contains the actual GDS. The supported prompt path still lacks that xmon
topology; the 64-case prompt population uses these frequencies only as scalar
conditioning seeds. A separate reference-geometry population below now checks
the published GDS directly. Electrical reproduction also needs materials,
ports, measured-device mapping and converged extraction.

### Original WM1 mask and measurement population

`scripts/validate_squadds_reference.py` downloads two small, pinned assets and
checks SHA-256 before parsing. `--offline` requires verified cached files.
The GDS revision is `5329ff178980c16a299caa4804a2e5251e326833`; the measurement
database revision is `0e25705f54c343fb96571ff15b6fd8375ca899aa`. Source URLs,
hashes, tool versions and comparison-code hashes are retained in
`benchmarks/squadds_reference/results.json`.

The fixed geometry population is all four top cells: `TOP`, `TOP$1`, `TOP$2`,
`TOP$3`. Each is imported/exported through gdsfactory and independently compared
using KLayout, including recursive geometry, every layer in either file,
database units, label content/placement and bounding box. Acceptance requires
empty XOR on every layer, identical labels and bounding box, and matching DBU.
All four 5 mm × 5 mm variants pass with zero XOR area on layers 5/0, 20/0,
60/0 and 703/0 in repeated runs. The original file has oversized GDS records;
KLayout's unsigned-record warnings are retained in execution logs.

The six-device WM1 measurement population is preserved verbatim as published
numeric fields, with attribution to the MIT-licensed SQuADDS database. The
design repository has no license file at the pinned revision, so the GDS is
fetched into ignored local storage rather than redistributed in this repository.
No upstream notebook code is executed.

The measured-to-top-variant mapping remains unknown. The database describes
aluminium on silicon and marks the fabrication recipe confidential; its
`sim_results` names datasets rather than providing the paired simulation values.
Geometry parity is therefore reported separately from **electrical reproduction
NOT_EVALUATED**, with null electrical errors. These measurements are not used to
calibrate the generic process or to claim measurement-validated generated layouts.

## 2. PalaceForCQED

Jiale Ye, Jiaheng Wang, Yu-xi Liu, **Electromagnetic Feature Extraction in
Superconducting Quantum Circuits: An Open-Source Finite-Element Workflow Using
Palace**, *2025 International Applied Computational Electromagnetics Society
Symposium (ACES-China)*, DOI 10.23919/ACES-China66523.2025.11332798.
[IEEE metadata](https://ieeexplore.ieee.org/document/11332798/),
[Table I, page 3](https://arxiv.org/pdf/2511.09041).

| Device | Simulated GHz | Measured GHz | Simulated coupling MHz | Measured coupling MHz |
| --- | ---: | ---: | ---: | ---: |
| R1 | 7.1933 | 7.1787 | 0.3600 | 0.3130 |
| R2 | 7.2861 | 7.2684 | 0.0960 | 0.0903 |
| R3 | 7.5604 | 7.5484 | 0.0916 | 0.1082 |
| R4 | 7.6551 | 7.6447 | 0.1740 | 0.2312 |

Reported limits: frequency error <0.3%; three of four couplings within 16%.
Setup: silicon epsilon_r=11.49, loss tangent 2.3e-6, 50-ohm ports, fourth-order
elements, refinement r=1.5. The paper does not supply complete numeric layout
coordinates in Table I. Exact GDS, ports, package and field-solver runs are
required before assigning our own comparison score. The measured frequencies
below are scalar seeds only.

## 3. SQDMetal (preprint, not counted as peer-reviewed)

David Sommers, Zach Degnan, Divita Gautam, Yi-Hsun Chen, Chun-Ching Chiu, Arkady
Fedorov, Prasanna Pakkiam, **Open-Source Highly Parallel Electromagnetic
Simulations for Superconducting Circuits**, arXiv:2511.01220v2 (2025).
[Table 1 and protocol](https://arxiv.org/html/2511.01220v2#S3.T1),
[open-source implementation](https://github.com/sqdlab/SQDMetal).

Single half-wave resonator: length 6.012 mm, epsilon_r=11.45. Table 1 gives
9.993 GHz (Palace AMR), 9.991 GHz (COMSOL), 10.004 GHz (HFSS), with reported
differences 0.020% and 0.110%. Palace AMR uses 69,301,924 degrees of freedom.
This is a field-solver convergence benchmark with a different topology from
our quarter-wave generator. Its values are comparison targets, not evidence
that the local analytical model attains equivalent accuracy.

## Metrics and acceptance rules

For positive reference y and prediction x:

- Signed relative error: `100 * (x-y)/y`; absolute percentage error (APE) is its
  absolute value. Delta between percentage scores is measured in percentage
  points, not percent change.
- RMS relative error: `100 * sqrt(mean(((x_i-y_i)/y_i)**2))`. References use
  measured values as denominators for our recomputation. The SQuADDS aggregate
  is quoted as published; its full paired simulation data was not reconstructed.
- Paper reproduction status is `NOT_EVALUATED` until geometry, physics,
  denominators and sample membership match, with fresh solver-owned outputs.
  A missing result is `null`, never zero, PASS, or a fabricated delta.
- Local geometry success = successful typed parse, verification, non-empty
  GDS/SVG/PNG/JSON outputs, and independent KLayout readback.
- Local target success additionally requires <=0.1% analytical target error.
  CPW error is independently evaluated from dimensions using SciPy elliptic
  integrals under the same thick-substrate, zero-thickness, lossless model.
  IDC, spiral and resonator target errors are model self-consistency checks.
- Local shorts/spacing checks are the existing net-aware geometry checks.
  Overlapping rectangles on the same conductor are not counted as shorts.
  We report evaluated-case counts so failed generation is not silently excluded.

## Standardized local population (64 cases, deterministic, no random seed)

`run_benchmark_validation.py` records every prompt and expected component/target
in its manifest. This is a new local engineering testbed, not a paper dataset.

| Family | Cases | Fixed input population |
| --- | ---: | --- |
| IDC | 16 | capacitance {0.2,0.4,0.6,0.8} pF × finger width {2,4} um × gap {2,3} um; 6 GHz |
| CPW | 16 | impedance {30,40,50,60} ohm × minimum gap {2,4,6,8} um; 6 GHz |
| Spiral | 16 | inductance {1,2,3,4} nH × turns {2,3,4,5}; width 4 um, spacing 2 um |
| Resonator | 16 | six SQuADDS and four PalaceForCQED measured frequency seeds above, plus {4,4.5,5,5.5,6,8} GHz; generic silicon quarter-wave geometry |

The generic technology uses epsilon_r=11.9. No prediction from this generic
geometry is compared numerically against either paper's measured device.
The suite intentionally disables external solvers for repeatable local sizing
checks; an installed-solver demo is a separate evidence stream.

## Open-source choices

### Additional reproducible paper-model population

S. S. Mohan, M. del Mar Hershenson, S. P. Boyd, T. H. Lee, **Simple Accurate
Expressions for Planar Spiral Inductances**, IEEE JSSC 34(10), 1419–1424 (1999),
DOI 10.1109/4.792620. [Author-hosted paper](https://web.stanford.edu/~boyd/papers/pdf/inductance_expressions.pdf).
This is a canonical analytical reference, not a recent SOTA claim.

`benchmarks/audit/mohan_1999.json` transcribes Table IV's 29 integer-turn square
spirals. All supported rows are included; fractional-turn and non-square
devices are excluded by schema/topology, without selection by error. The
transcription was checked against a rendered PDF table. Row 18's measurement
is 8.00 nH, and row 36's Wheeler error is 3.9% (adjacent columns must not be
mistaken for these values).

For each row, compute `d_in = d_out - 2*n*w - 2*(n-1)*s`,
`d_avg = (d_out+d_in)/2`, `rho = (d_out-d_in)/(d_out+d_in)`, and
`L = 2.34*mu0*n^2*d_avg/(1+2.75*rho)` with dimensions in SI units.
The paper's error sign is `100*(measured-model)/measured`, opposite to the
signed prediction error defined earlier. Compare this error with the printed
modified-Wheeler column. A 0.5 percentage-point allowance accommodates the
printed dimensions/coefficients; it is a **model reproduction** tolerance,
not a 0.5% measurement-accuracy claim. Preserve the full measurement residuals.

Results: 29/29 model rows reproduced; maximum column deviation 0.2146 pp.
RMS measurement error is 8.9787% for the printed column and 8.9369% for the
implementation. Worst measurement APE remains 19.749%. Small differences from
printed coefficients do not constitute a new performance result.

### Optional fresh FastHenry population

`--with-fasthenry` executes all 16 local spiral cases, using the existing
solver adapter and bounded target-retuning loop with its 5% tolerance. It
requires a real executable, successful process completion, retained `Zc.mat`,
parsed positive inductance and successful GDS checks. Missing solvers and failed
cases remain in the denominator. Native installer revision:
`363e43ed57ad3b9affa11cba5a86624fad0edaa9` from
[FastHenry upstream](https://github.com/ediloren/FastHenry2).

This separate population checks normal-metal geometric inductance at the
deck's lowest frequency (1 MHz), generic conductivity 5.8e7 S/m, and 0.2 um
thickness. FastHenry divides its input conductivity by the length-unit scale;
the micrometre-unit deck therefore specifies `sigma=58`. The original `5.8e4`
value implied 5.8e10 S/m and understated resistance by 1000x. Two unchanged
real-solver/Ohm's-law checks reproduced that defect before it was corrected.
The DSL exposes `conductivity_s_per_m` for explicit process inputs.
These generic assumptions are not a superconducting process
model. The current benchmark is not a filament/mesh-convergence study and does
not compare these new layouts with the Mohan measurements.

Both the 64-case geometry grid and the 16-case solver run passed repeated
execution. File hashes establish artifact identity; timestamps, absolute output
paths and timing logs naturally vary between runs. Repeatability compares the
same source-tree hash, parameters, decisions and numerical quantities; see
`benchmarks/audit/repeatability.json`.

Reuse the existing gdsfactory/KLayout exports and net-aware verifier. For a
reproduced CPW sizing gap, use
[SciPy Brent root finding](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.brentq.html)
and constraint-aware dimensional scaling, retaining analytical evidence status.
The existing optional
[scikit-rf CPW model](https://scikit-rf.readthedocs.io/en/latest/api/media/generated/skrf.media.cpw.CPW.analyse_quasi_static.html)
provides a finite-substrate correlation, not a field solver. Reuse the existing
JoSIM adapter for actual circuit transients if the public macOS binary installs.
