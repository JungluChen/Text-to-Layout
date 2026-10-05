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

## Predeclared LC acceptance gate

`scripts/check_circuitq_lc.py --out NEW_DIRECTORY` runs two fixed physical cases
(C=80 fF, L=80 nH; C=120 fF, L=60 nH). The immutable plan is
`references/circuitq/lc-plan.json`, declared before executing these cases.
Grid sizes 401/801/1601 cover +/-8 Gaussian flux standard deviations; a
2001-point +/-10-sigma domain keeps the final spacing fixed for a boundary check.
Limits: 20 ppm frequency/reference, last refinement and alpha/frequency;
0.1 ppm domain effect; 1e-10 scaled eigenpair residual; 1e-13 Hermiticity.
These are numerical resolution requirements, not measured uncertainty.

Initial SI diagonalization failed the residual limit twice (maximum ~1.286e-7)
even though its frequencies satisfied their limits. Those rejected runs remain
retained. The accepted representation uses upstream `natural_units=True`:
energy scale = upstream hbar * 1e9 J, flux scale = upstream hbar/(2e) Wb,
C_natural=C*energy_scale/(2e)^2 and L_natural=L*energy_scale/flux_scale^2.
The domain is converted by flux_scale. Natural energies are converted back to
joules before dividing by exact Planck h to obtain Hz.

Every discretized natural matrix, scaled back to joules, is compared to the SI
matrix (relative Frobenius difference <1e-12). This preserves the physical
Hamiltonian while improving solver conditioning; no reference or scientific
threshold was changed. Natural-unit repeats had residuals below 1.5e-16 and
matrix differences below 1.6e-13. Frequency error is about 6.251 ppm, last
refinement about 18.751 ppm, and domain effect below 5e-12 relative.

From the repository root, with the audited checkout installed in the isolated
runtime described in the previous report:

```sh
/private/tmp/textlayout-circuitq-runtime/bin/python scripts/check_circuitq_lc.py --out /tmp/circuitq-first
/private/tmp/textlayout-circuitq-runtime/bin/python scripts/check_circuitq_lc.py --out /tmp/circuitq-repeat
```

Save stdout/stderr with both runs. Inspect plan.json and report.json, upstream
core hash, dependency versions, matrices' similarity, raw joule eigenvalues and
all metrics. Exit 0 requires every gate; failure is retained as rejection.
Output directories must be new. This developer gate does not expose a product
CLI/MCP function or promote canonical evidence. Typed adapter and actual
Windows/macOS/Linux runs are next; checklist entry 004 remains unchecked.
AI prompt: “Run the locked LC benchmark twice, explain why the SI eigenpair
residual was rejected, and check physical-matrix equivalence before interpreting
the natural-unit result. Do not call this EM or measurement validation.”

[Retained failure, diagnosis and verification](../progress/2026-10-05-101038.md).

## Typed product command

`textlayout.external.circuitq_lc.LCRequest` requires explicit capacitance_f
(80–120 fF in farads) and inductance_h (60–80 nH in henries); no defaults,
nonfinite values or extra fields. `run_lc(request, python=..., output_dir=...)`
uses a process-isolated optional CircuitQ runtime. Input bounds are a bounded
operating scope, not a claim that the whole domain has platform acceptance.
The same fixed numerical checks apply to every request.

Install the audited upstream source in a separate environment:

```sh
uv venv /tmp/circuitq-runtime --python 3.12
uv pip install --python /tmp/circuitq-runtime "circuitq @ git+https://github.com/PhilippAumann/circuitq.git@b45978891ac2c25ad7a44973c3cbe836c770e0aa"
uv run --no-sync textlayout circuitq-lc examples/integrations/circuitq-lc-a.json --python /tmp/circuitq-runtime/bin/python --out out/circuitq-a-first
uv run --no-sync textlayout circuitq-lc examples/integrations/circuitq-lc-a.json --python /tmp/circuitq-runtime/bin/python --out out/circuitq-a-repeat
uv run --no-sync textlayout circuitq-lc examples/integrations/circuitq-lc-b.json --python /tmp/circuitq-runtime/bin/python --out out/circuitq-b-first
uv run --no-sync textlayout circuitq-lc examples/integrations/circuitq-lc-b.json --python /tmp/circuitq-runtime/bin/python --out out/circuitq-b-repeat
```

Windows interpreter path: `ENV/Scripts/python.exe`. Retain request.json,
solver.json, manifest.json and both logs. Worker checks version and audited
core hash (normalizing CRLF only for source identity; raw hash also retained).
No upstream code is vendored. Each packet records SI/natural matrix equivalence,
raw joule energies, frequency/anharmonicity in Hz, refinements, residuals,
dependency versions, input/output hashes and actual command arguments.

`execution_completed` and `numerical_checks_passed` are distinct. Accepted
quantities use canonical `SIMULATION_EXECUTED`; failed numerical gates expose
no accepted quantities and use `CONVERGENCE_FAILED`. Malformed output is
`SIMULATION_INVALID`, launch/timeout failure is `FAILED`. Neither exact LC
agreement nor a successful process establishes EM or measurement validation.
Fresh output directory required; same-input retry and edited requests are
separate invocations. API timeout defaults to 120 seconds and retains partial
logs. No solver checkpoint/resume, GUI, screenshot or MCP command is exposed.

AI prompt: “Run both typed LC examples twice with the audited external
interpreter. Inspect SI/natural matrix equality, raw energies, residual and
grid/domain checks before interpreting the result. Report rejected output
without promoting it to physical validation.”
