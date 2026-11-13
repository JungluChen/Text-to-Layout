# FasterCap and FastHenry2 validation status

**Status: analytical references and prepared geometry only. Numerical solver
agreement and convergence are pending.** The former 4% / 1.8% FasterCap and
2.5% / 2.1% FastHenry2 claims came from hard-coded scaling of analytical
formulas in `tests/textlayout_suite/test_field_solvers.py`; they were not
solver outputs and are withdrawn.

The tests retain a parallel-plate analytical reference, IDC formula, loop and
spiral inductance formula, and a `.qui` coordinate check showing 100 µm maps
to 1e-4 m and 2 µm to 2e-6 m. This establishes neither full input validity nor
execution. The test-only `.qui` panels are not a completed production
FasterCap handoff.

For FasterCap, prepare a valid multi-conductor CPW and parallel-plate case,
retain the binary version/hash, solver-owned capacitance matrix and logs, and
repeat at three panel resolutions. Compare compatible capacitance definitions
with a separately sourced analytical or published reference under predefined
error and convergence limits. For FastHenry2, retain conductor geometry,
frequency, material assumptions, binary version/hash, solver-owned impedance
or inductance and logs at three filament refinements. Do not infer
superconducting kinetic inductance from a classical PEEC result.

Only after those records exist should either target gain numerical acceptance
in the integration checklist. Package import and Docker build status do not
establish solver accuracy.
