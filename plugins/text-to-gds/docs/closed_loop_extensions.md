# Measurement, Packaging, Materials, EM Routing, and Readiness

These five tools extend the closed loop from layout/EM into measured-data
fitting, package parasitics, superconducting-material modelling, EM-backend
routing, and a technology-readiness score. Each is local and deterministic;
optional SciPy refinement is used only when it is installed and never claimed
otherwise.

## Measurement fitting (`fit_measurement`)

Fits a measured or simulated trace (CSV or JSON) into device metrics and can log
the result to the experiment database for the next-design correction.

- Resonator (notch/hanger): `f0`, internal `Qi`, coupling `Qc`, loaded `Ql`.
- JPA gain: peak gain, center frequency, 3 dB bandwidth, gain-bandwidth product.
- Pump sweep: oscillation threshold and pump-at-20 dB.
- Noise: minimum noise temperature versus the quantum limit and added quanta.

```powershell
py -3 -m uv run python -c "from text_to_gds.server import fit_measurement; print(fit_measurement('workspace/artifacts/S21.csv', fit_kind='resonator', device_id='RES-001'))"
```

Recognized CSV columns are case-insensitive (`frequency_ghz`/`freq_mhz`/`freq_hz`,
`s21_db`/`s21_mag`/`s21_re`+`s21_im`, `gain_db`, `noise_temperature_k`,
`pump_fraction`). `fit_kind=auto` infers the fit from the available columns. The
Kerr coefficient and pump efficiency require a harmonic-balance pump sweep
(`export_jpa_analysis`), not a single gain trace.

## Superconducting material and kinetic inductance (`export_superconducting_material`)

Computes sheet kinetic inductance from the London penetration depth and film
thickness (`Ls = mu0 lambda coth(t/lambda)`) or from the normal-state sheet
resistance and `Tc` (Mattis-Bardeen `Ls = hbar Rn / (pi Delta)`,
`Delta = 1.764 kB Tc`), or a process-material default. With a trace width/length
it reports total `Lk`; with a geometric inductance from EM it reports the kinetic
participation. It also emits the thin-strip current-crowding profile.

```powershell
py -3 -m uv run python -c "from text_to_gds.server import export_superconducting_material; print(export_superconducting_material(material='NbTiN', thickness_nm=100, tc_k=14, rn_sheet_ohm=100, trace_width_um=1.0, trace_length_um=100.0, geometric_inductance_ph=50.0))"
```

## Package model (`export_package_model`)

First-order chip/wirebond/PCB/package/connector parasitics: Grover bondwire
inductance (with parallel-wire mutual coupling), rectangular-cavity package
modes, the bondwire series reactance at the operating frequency, optional
self-resonance with a coupling capacitor, and warnings when a package mode falls
near the operating band.

```powershell
py -3 -m uv run python -c "from text_to_gds.server import export_package_model; print(export_package_model(operating_frequency_ghz=6.0, bondwire_length_um=800, bondwire_count=4, bondwire_pitch_um=100, package_width_mm=6, package_length_mm=6, package_height_mm=3))"
```

## EM solver routing (`list_em_solvers`, `recommend_em_solver`)

A unified `EMSolver` layer wraps the openEMS, HFSS (PyAEDT), and Sonnet bridges
and routes a device by geometry class: planar superconducting structures (CPW,
IDC, resonators) prefer Sonnet, full 3D and packaging prefer HFSS, and the
open-source default is openEMS. Any backend can run any structure; the routing
only orders them by typical suitability.

```powershell
py -3 -m uv run python -c "from text_to_gds.server import recommend_em_solver; print(recommend_em_solver(device_type='cpw_resonator'))"
```

## Readiness score / TRL (`run_validation_checklist`)

The validation checklist now adds an `electromagnetic` and a `measurement`
section and a `readiness` block. The technology-readiness level is *gated*: it
advances only while each contiguous upstream stage (Layout -> DRC -> Extraction
-> Circuit simulation -> EM extraction -> Measurement) meets the 80% evidence
threshold, so downstream evidence cannot inflate the level past an unmet upstream
gate. The toolkit caps at TRL 7; TRL 8-9 need system qualification beyond these
artifacts.

```powershell
py -3 -m uv run python -c "from text_to_gds.server import run_validation_checklist; print(run_validation_checklist(sidecar_path='workspace/artifacts/ljpa_seed.sidecar.json')['readiness'])"
```
