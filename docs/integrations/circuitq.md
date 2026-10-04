# CircuitQ — entry 004, audit and exploratory execution

Document class: MANUAL_DOCUMENTATION. Not a completed integration.

Source: [PhilippAumann/circuitq](https://github.com/PhilippAumann/circuitq/tree/b45978891ac2c25ad7a44973c3cbe836c770e0aa),
revision b45978891ac2c25ad7a44973c3cbe836c770e0aa; setup.py declares 1.2.1,
MIT license. Dependencies: NumPy, NetworkX, SymPy and SciPy, unbounded upstream.
Isolated Python 3.12 installation resolves/imports successfully; keep it outside
the lean base package. No canonical CircuitQ adapter was found in this repository.

The upstream LC notebook provides a parallel C/L graph. Explicit ground node 0,
SI mode, C=1e-13 F and L=1e-7 H were used for the first probe. These are upstream
default values, not extracted layout parameters. Hamiltonian energies are J;
f01=(E1-E0)/h, with exact h=6.62607015e-34 J s. Independent ideal-circuit reference
is 1/(2 pi sqrt(LC)) = 1591549430.9189532 Hz. Upstream hbar is rounded to
1.054571817e-34 J s and its phi_0 denotes hbar/(2e), not h/(2e). Preserve that
convention explicitly. Even requested grid dimensions are raised to the next
odd value; never record only the requested dimension.

Two unchanged runs returned identical tables:

| Grid | f01 Hz | Relative error |
| --- | --- | --- |
| 101 | 1578536068.1593983 | -0.00817653697 |
| 201 | 1588316252.5510495 | -0.00203146588 |
| 401 | 1590742370.3297112 | -0.00050709112 |

This decreasing error is exploratory evidence consistent with second-order
finite differences, not a completed convergence or boundary-error bound.
No pass threshold was applied retrospectively. The probe projects eigenvalues
to real for inspection; a production parser must retain/check imaginary parts,
Hermiticity, residuals and finite values before acceptance.

Next: declare a fresh LC benchmark with explicit physical parameters, grid and
domain refinement, exact frequency/zero anharmonicity reference, and numerical
limits before execution. Inspect periodic/end-point discretization assumptions
and parameter ordering. Then implement a typed isolated adapter, repeat via the
product interface, verify each platform and retain canonical evidence. No EM,
T1/noise, arbitrary-topology or measurement claim follows from this LC probe.

[Full audit and reproduction report](../progress/2026-10-05-040848.md). No product CLI or
MCP command exists yet. AI prompt: “Inspect CircuitQ's parameter ordering, SI and
reduced-flux conventions, grid/domain refinement and residuals before proposing
an acceptance benchmark. Do not promote import or exploratory output.”
