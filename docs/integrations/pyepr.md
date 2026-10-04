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

## Next acceptance steps

1. Establish which charge-boundary/charge-dispersion approximation the chosen
   pyEPR path supports. Preserve the zero-charge discrepancy.
2. Specify a physically aligned independent benchmark and its numerical/model
   tolerances before running a new case. Do not turn approximate band-centre
   agreement into an exact ng=0 validation claim.
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
