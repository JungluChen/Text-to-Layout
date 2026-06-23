# Physics Compiler Status

## Completed

- Added typed `extracted_device.json` workflow in `src/text_to_gds/extracted_device.py`.
- Extracts GDS polygons, per-layer metal area, conductor width/length, minimum spacing, and port count.
- Extracts JJ area and computes `Ic = Jc*A`, `Lj = Phi0/(2*pi*Ic)`, optional `Cj = Cs*A`, and `wp = 1/sqrt(Lj*Cj)`.
- Extracts CPW per-length values: `C' = 1/(Z0*vp)`, `L' = Z0/vp`, `Z0 = sqrt(L'/C')`, `vp = 1/sqrt(L'C')`, and `f0 = vp/(4*l)`.
- Added Pydantic models for extracted quantities, solver lifecycle reports, microwave reports, and optimization reports.
- Added solver lifecycle abstraction in `src/text_to_gds/solver_interfaces.py` with `prepare()`, `run()`, `parse()`, and `validate()`.
- Added lifecycle wrappers for FastCap, FastHenry, and openEMS. Missing binaries return `status="skipped"` and do not generate substitute data.
- Added `src/text_to_gds/microwave_validator.py` to produce `microwave_report.json` with reciprocity, energy conservation, stability, and resonance extraction.
- Replaced `src/text_to_gds/jpa_physics.py` with a compatibility shim that refuses custom JPA gain simulation and points callers to JosephsonCircuits.jl.
- Added `src/text_to_gds/backends/` as the universal orchestration layer for KQCircuits, Qiskit Metal, gdsfactory, scqubits, JosephsonCircuits.jl, openEMS, Palace, Elmer, and pyEPR.
- Patched SuperCAD layout backend selection so KQCircuits/Qiskit Metal/gdsfactory no longer emit empty placeholder GDS files.
- Added `src/text_to_gds/device_optimizer.py` with `optimize_device()` for CPW width/gap tuning, IDC tuning, and JJ area tuning.
- Added pytest coverage in `tests/test_physics_compiler_loop.py`.

## Remaining

- FastCap and FastHenry need installed solver binaries plus calibrated substrate/dielectric panel models before capacitance/inductance signoff.
- openEMS needs a device-specific CSX geometry/port exporter for production-grade S-parameter runs beyond the current XML runner path.
- KQCircuits and Qiskit Metal still need verified element-to-GDS export implementations for production layouts; current adapters prepare plans and fail/skip honestly.
- JPA gain must come from JosephsonCircuits.jl or measured pump sweeps; custom gain simulation is disabled.
- IDC layout extraction should move from optimizer formula to geometry-derived finger extraction.
- Optimization loop should call real extraction plus solver adapters for closed-loop EM repair when binaries are available.

## Physics Confidence

- JJ area/Ic/Lj: high for GDS geometry and analytical small-signal formulas when `Jc` is calibrated.
- CPW Z0/f0: medium; geometry-backed analytical CPW values are useful for synthesis, but EM verification is still required.
- JPA gain/bandwidth/P1dB: no local confidence without JosephsonCircuits.jl or measured pump sweeps.
- FastCap/FastHenry values: unavailable in this environment because binaries are not on PATH.

## Solver Availability

- openEMS adapter: available through the Python adapter probe.
- scqubits: Python import available.
- JosephsonCircuits.jl adapter: unavailable in current probe.
- FastCap: not on PATH.
- FastHenry: not on PATH.
- JoSIM: not on PATH.
- ngspice: not on PATH.
- Julia: not on PATH.

## Next Required Calibration

- Process-specific `Jc` and JJ specific capacitance `Cs`.
- CPW substrate stack: dielectric constant, thickness, conductor thickness, kinetic inductance, and loss tangent.
- FastCap/FastHenry mesh/panel density validation against a known coupon.
- openEMS port calibration and boundary-condition validation against a measured or literature CPW resonator.
- JPA pump calibration: pump coupling, external kappa, internal loss, saturation power, and flux-bias dependence.
