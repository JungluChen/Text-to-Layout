# SQcircuit — entry 006, source and numerical audit only

Document class: MANUAL_DOCUMENTATION.

Source: https://github.com/stanfordLINQS/SQcircuit/tree/7cdc826a63224a8fb860362224a4a530e80aa1d7
(tag v1.0.0, distribution 1.0.0), BSD-3-Clause. The old squadds/SQcircuit
hint returned 404 twice; the inventory now identifies the actual upstream.
Installed circuit.py and units.py match the pinned source hashes in the retained
audit. Methods paper: Quantum 7, 1118 (2023), DOI 10.22331/q-2023-09-25-1118.
This citation is not a completed paper or experimental comparison.

Mandatory dependencies include PyTorch, QuTiP, NumPy, SciPy, SymPy, mpmath,
matplotlib, dill and IPython. An isolated temporary Python 3.12 environment
installed the package; no base dependencies changed and no native tools were
vendored. The resolved SymPy 1.14.0rc1 is a prerelease and is not an approved
production dependency pin. Full versions are in the retained audit packets.

Explicit F/H inputs avoid upstream GHz element defaults. Upstream uses rounded
hbar, Phi0 and e; a future typed adapter must expose the resulting convention.
The initial two-case LC probe used truncations 10/20/30 and six levels, with
predeclared diagnostic 1 Hz reference resolution and 1e-12 scaled residual.
Both unchanged runs failed the ideal capacitor-only reference: maximum errors
were approximately 397.887 and 717.876 Hz. Exit zero was not scientific success.

Diagnosis: Inductor defaults to VerySmallCap, adding 1e-20 F in parallel.
The resolved capacitance matrix exactly contains C + 1e-20 F. Re-evaluating the
saved levels against 1/(2*pi*sqrt((C+1e-20)*L)) gives worst discrepancy
0.0000762939453125 Hz. This is a post-hoc model diagnosis, not replacement
acceptance evidence. Preserve the original failed plan and results.
Unchanged-run levels differed by at most 0.00004100799560546875 Hz. The upstream
sparse eigensolver supplies no initial vector; NumPy seed 0 did not produce
bitwise identical output. Residuals were below 6e-16. Determinism policy and
explicit model parameters need resolution before a production adapter.

Evidence: ../progress/evidence/2026-10-10-211726/ (hash manifest included).
No typed adapter, canonical execution packet or Windows/Linux verification is
accepted. Checklist entry 006 stays unchecked. Next: establish explicit branch
capacitance semantics and stable compatible pins, lock an a priori reference
plan, implement the typed adapter and canonical provenance, then run unchanged
benchmarks twice on all three platforms. No EM, noise or measured-device claim.
