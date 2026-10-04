# pyEPR — checklist entry 003, numerical acceptance pending

Document class: MANUAL_DOCUMENTATION.

The source is [zlatko-minev/pyEPR](https://github.com/zlatko-minev/pyEPR/tree/97be9f15212e6ddd427e7ee310dacfa778240fe0),
release 1.0.2 / pyEPR-quantum 1.0.2, BSD-3-Clause. The existing legacy live-HFSS
path remains disabled. This audit executes the upstream numerical Hamiltonian
function directly, without HFSS, field extraction, paid services or fabricated
participation ratios. It does not turn specified circuit parameters into
simulated 3-D geometry evidence.

## Findings before adapter implementation

The real `epr_numerical_diagonalization` operation accepts linear frequency in
GHz, junction inductance in H and dimensionless reduced phase ZPF. Its current
return docstring says dressed frequency in GHz, but actual return values and
returned Hamiltonian differences are in Hz. Chi is in MHz with a positive
red-shift convention. An adapter must distinguish positive chi from signed
negative anharmonicity and retain both raw values and explicit conversions.

The recorded one-mode example uses EJ/h=20 GHz and EC/h=0.3 GHz, derived
linear frequency sqrt(8 EJ EC)/h, Lj=(hbar/2e)^2/EJ and phase ZPF
(2 EC/EJ)^(1/4). Actual full-cosine Fock runs at 12/18/24/30 levels repeat
unchanged. Independent charge-basis diagonalization uses
H/h=4(EC/h)(n-ng)^2-(EJ/h)cos(phi), with charge cutoffs 15/25/35.
These are input-defined ideal circuit models, not extracted device values.

At Fock 30, f01=6613448457.664044 Hz and signed alpha=-336877607.14520246 Hz.
At charge cutoff35 and ng=0, f01=6613448853.504728 Hz and
alpha=-336893105.5761452 Hz. The discrepancy persists after basis refinement.
A controlled ng sweep supports a charge-band/boundary-condition explanation;
it is not a validated defect diagnosis or permission to select a better-fitting
reference after seeing results. The ng=0.25 diagnostic nearly matches the
localized oscillator calculation, but remains diagnostic only.

Methods to review: [Koch et al. (2007)](https://arxiv.org/abs/cond-mat/0703002v2)
and [Minev et al. (2021)](https://arxiv.org/abs/2010.00620v3). These references
support model analysis, not a claim that the chosen numbers reproduce a
published measurement. Exact inputs, dependency versions, repeated numerical
tables, source/probe hashes and commands are in
[the dated report](../progress/2026-10-04-110110.md).

## Reproducible ideal-circuit benchmark

The new gate fixes EJ/h, EC/h to (30 GHz, 150 MHz) and (40 GHz, 160 MHz),
ratios 200 and 250. The immutable plan is
`references/pyepr/charge-insensitive-plan.json`, declared before those runs.
Both cases compare full-cosine Fock cutoffs 16/24/32/40 against independent
charge cutoffs 25/35/45 at ng=0, 0.25 and 0.5. Each final refinement must change
f01 and signed alpha by at most 1 Hz; the sampled charge-offset spread must be
at most 1 Hz, and maximum cross-method difference at most 2 Hz. These are
numerical requirements, not experimental uncertainty or a general error bound.
Three sampled offsets do not establish an exhaustive dispersion bound.

The script additionally checks raw return units/signs against Hamiltonian
eigenvalue differences, rejects missing/nonfinite samples, and retains imaginary
residues and the anti-Hermitian matrix residual. Floating-point noise is bounded
by 32 binary64 epsilon times scale; materially complex results fail. This
roundoff handling does not alter the scientific comparison thresholds.

Run from the repository root in a separate environment:

```sh
uv venv --python 3.12 /tmp/textlayout-pyepr-benchmark
uv pip install --python /tmp/textlayout-pyepr-benchmark/bin/python pyEPR-quantum==1.0.2
/tmp/textlayout-pyepr-benchmark/bin/python scripts/check_pyepr_charge_insensitive.py --out /tmp/pyepr-first
/tmp/textlayout-pyepr-benchmark/bin/python scripts/check_pyepr_charge_insensitive.py --out /tmp/pyepr-repeat
```

Keep command stdout/stderr alongside each directory. Exit 0 requires all gates;
exit 1 indicates a rejected result. The output directory must be new. Inspect
`plan.json`, `report.json`, dependency identities, raw returns, eigenvalues,
refinements and every metric before interpreting `passed`. No HFSS, EM fields,
geometry, measured reference, GUI, MCP command or product adapter is supplied.
Canonical evidence is explicitly not promoted. On Windows the external Python
path differs; actual numerical platform validation remains pending.

Two unchanged local runs pass with a maximum comparison difference below
0.0032 Hz. The earlier ratio-66.7 ng=0 mismatch remains retained and unaccepted.
A successful high-ratio example does not validate that earlier case. See
[the benchmark report](../progress/2026-10-04-131811.md).

Recovery: preserve a rejected packet, repeat unchanged into a fresh directory,
compare the retained versions/inputs and diagnose before modifying anything.
Do not modify the locked plan to obtain a pass. AI prompt: “Run the two fixed
pyEPR ideal-circuit benchmarks twice. Explain the charge-boundary approximation,
raw frequency/chi units, convergence and failures; keep EM and measurement
validation explicitly pending.”

## Next acceptance steps

1. Preserve the zero-charge discrepancy and the accepted two-case benchmark
   scope; do not generalize the sampled charge-insensitive approximation.
2. Retain the fixed reference/convergence gate when implementing the adapter.
3. Implement typed input/output units and explicit model assumptions. Preserve
   upstream raw numbers, sign convention, version, Hamiltonian and convergence.
4. Repeat accepted reference/convergence checks through the product adapter
   and on each supported platform before marking this entry complete.

The current isolated environment is `/private/tmp/textlayout-pyepr-102`; the
retained probe snapshots in the report can be copied to .py files and executed
with that interpreter into fresh directories. No new CLI/MCP command is exposed.
AI prompt: “Audit the pyEPR return units and circuit boundary assumptions against
its raw Hamiltonian and the independent charge reference. Explain the retained
difference without relabelling it as validation or relaxing acceptance gates.”
