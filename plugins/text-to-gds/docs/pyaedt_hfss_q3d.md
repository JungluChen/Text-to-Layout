<!-- Moved out of the top-level README to keep it focused. -->

# PyAEDT HFSS And Q3D Simulation

This is the industry-EM path: GDS geometry is mapped onto the process stack and
handed to Ansys HFSS and Q3D through PyAEDT 1.1+. Generation is license-free and
returns `status: prepared`; populating the *solved* fields below requires a
licensed Ansys Electronics Desktop install (`run=True, solve=True`). The numbers
and figures in this section that do **not** need a license were produced for real
on the bundled `readiness_demo` LJPA; the solved HFSS/Q3D quantities are shown as
their result schema plus the published benchmark targets they are checked
against, and cross-checked with the open-source openEMS FDTD solver.

## Functions

| Function | Role | Key output |
| --- | --- | --- |
| `export_hfss_project` | HFSS driven-modal + eigenmode script for the GDS | `f0`, `Q`, S-parameters |
| `export_pyaedt_project` | Full HFSS + Q3D automation bundle | S-parameters, eigenmodes, C-matrix, field images |
| `export_q3d_extract` | Q3D Maxwell/coupling capacitance extraction | $C_{ij}$ matrix (pF) |
| `recommend_pyaedt_design_correction` | Turn EM error into a geometry seed | length/cap/gap scale factors |
| `run_pyaedt_design_iteration` | Apply one correction, regenerate GDS, run DRC | corrected `.gds` + DRC |
| `run_pyaedt_benchmarks` | Compare a solved result against paper targets | pass / fail / skip |

## Equations

GDS-to-3D stack mapping (`import_gds_3d`): layer $n$ is extruded at elevation
$z_n=\sum_{i<n} t_i$ with thickness $t_n$; metals become PEC in HFSS and copper
in Q3D, dielectrics keep $(\varepsilon_r,\tan\delta)$.

CPW propagation extracted from the solved field (driven-modal / openEMS):

$$\varepsilon_{\text{eff}}=\left(\frac{c\,\beta}{\omega}\right)^{2},\qquad v_p=\frac{c}{\sqrt{\varepsilon_{\text{eff}}}},\qquad Z_0=\sqrt{\frac{L}{C}},\qquad \lambda_g=\frac{v_p}{f}$$

HFSS eigenmode resonance, quality factor, and dielectric participation:

$$f_0=\frac{1}{2\pi\sqrt{LC}},\qquad Q=\frac{\omega_0 U}{P_{\text{loss}}},\qquad \frac{1}{Q}=\sum_i p_i\tan\delta_i,\qquad p_i=\frac{U_i}{U_{\text{tot}}}$$

Q3D Maxwell capacitance matrix (`export_q3d_extract`):

$$Q_i=\sum_j C_{ij}V_j,\qquad C_{ij}=C_{ji}$$

EM geometry correction (`recommend_pyaedt_design_correction`): since
$f_0\propto 1/\sqrt{LC}$ and $Z_0\propto\sqrt{L/C}$,

$$s_{\text{length}}=\frac{f_{\text{extracted}}}{f_{\text{target}}},\qquad s_{C}=\left(\frac{f_{\text{extracted}}}{f_{\text{target}}}\right)^{2},\qquad s_{\text{gap}}=\sqrt{\frac{Z_{\text{target}}}{Z_{\text{extracted}}}}$$

For example, a solved $f_0=5.18$ GHz against a 5.0 GHz target with $Z_0=46\,\Omega$
returns a +3.6% frequency error, a 1.036 CPW-length scale, and a 1.043 gap seed.

## 3D model (HFSS import geometry)

`export_pyaedt_project` extrudes each GDS layer onto the process stack before
`import_gds_3d` builds it in HFSS/Q3D. The render below is the real
`readiness_demo` geometry (25 shapes) on the generic Nb/SIS stack; the vertical
axis is exaggerated 60x so the sub-micron films are visible.

![HFSS import 3D stack model](assets/hfss_stack_3d.png)

| GDS layer | Name | Elevation (um) | Thickness (um) | HFSS material | Q3D material |
| --- | --- | --- | --- | --- | --- |
| 3 | M1 | 0.000 | 0.180 | PEC | copper |
| 4 | JJ | 0.180 | 0.002 | AlOx ($\varepsilon_r$ 9) | AlOx |
| 5 | M2 | 0.182 | 0.200 | PEC | copper |
| 6 | M3 | 0.382 | 0.350 | PEC | copper |
| 7 | VIA12 | 0.732 | 0.200 | PEC | copper |
| 8 | VIA23 | 0.932 | 0.250 | PEC | copper |

Substrate: high-resistivity silicon, $\varepsilon_r$ 11.45, 500 um.

## Generated project (real, license-free)

```powershell
py -3 -m uv sync --extra hfss
py -3 -m uv run python -c "from text_to_gds.server import export_pyaedt_project; print(export_pyaedt_project('workspace/artifacts/readiness_demo.gds', sidecar_path='workspace/artifacts/readiness_demo.sidecar.json', output_name='readiness_demo'))"
```

Returns `status: prepared` and writes a config plus two PyAEDT scripts that
compile and embed the current API (`import_gds_3d`, `create_setup`,
`create_linear_count_sweep`, `export_touchstone`, `create_fieldplot_volume`;
`Q3d` + `export_matrix_data`). The generated setup for `readiness_demo`:

- Ports: `rf_in`, `rf_out` (lumped, 50 ohm), flagged `review_required`.
- Driven sweep: 1-12 GHz, 221 points, 12 adaptive passes, $\Delta S$ 0.02.
- Eigenmode: 4 modes from 3 GHz.

## Simulation result (requires licensed AEDT)

A `run=True, solve=True` run populates this schema; the targets are what
`run_pyaedt_benchmarks` checks a solved result against (from published devices):

| Benchmark | Analysis | Result key | Target | Tolerance |
| --- | --- | --- | --- | --- |
| `07_hfss_resonator` | HFSS eigenmode | `frequency_ghz`, `quality_factor` | 6.0 GHz, 20000 | 1% / 10% |
| `08_hfss_jpa` | HFSS driven-modal | `frequency_ghz`, `impedance_ohm` | 6.0 GHz, 50 ohm | 1% / 5% |
| `09_hfss_idc` | Q3D capacitance | `capacitance_pf` | 0.6 pF | 3% |

Without a license the suite is honest about it:

```text
run_pyaedt_benchmarks -> status: prepared, counts: {passed: 0, failed: 0, skipped: 3}
```

Solved runs also export `.s2p` (driven-modal S-parameters), an eigenmode JSON
(`f0`, `Q`), a Q3D capacitance CSV, and `Efield.png` / `Hfield.png` /
`current_density.png` field images.

## openEMS FDTD cross-check (real, no license)

The requested 10 um trace width runs in the open-source openEMS canonical
microstrip model, which produces the same class of S-parameter and impedance
outputs as HFSS driven-modal. It is a transmission-line cross-check, not a full
GDS-equivalent CPW solve:

![openEMS FDTD extraction for the same geometry](assets/hfss_openems_cross_check.png)

| Quantity | openEMS FDTD (`readiness_demo`) |
| --- | --- |
| Effective permittivity (6.0005 GHz) | 6.558 |
| Characteristic impedance $Z_0$ (estimate) | 133.0 ohm |
| Return loss $S_{11}$ (6.0005 GHz) | -6.64 dB |
| Insertion loss $S_{21}$ (6.0005 GHz) | -5.67 dB |
| Frequency band / points | 0-12 GHz / 201 |
| Validated reporting band | 1.2-12 GHz |
| E-field VTK dumps written | 98 |

Generated lumped-port sheets, mesh convergence, substrate loss tangents, and the
default PEC/copper conductor substitutions are mandatory review gates. They are
not signoff evidence until replaced with calibrated process models. Frequencies
below 10% of the configured maximum are excluded from passivity and
permittivity validation because the Gaussian excitation and port extraction are
not reliable there. The adapter checks
$|S_{11}|^2+|S_{21}|^2\leq1$ in the validated band. openEMS still uses a
microstrip-port approximation pending coplanar ports and a kinetic-inductance
metal model (see `export_superconducting_material`).

