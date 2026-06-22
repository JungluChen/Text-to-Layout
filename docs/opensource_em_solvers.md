<!-- Moved out of the top-level README to keep it focused. -->

# Open-Source EM Solvers (Palace, Elmer, FastHenry/FastCap, gmsh)

Beyond openEMS, Text-to-GDS routes to a full open-source EM stack so the HFSS/Q3D
functions have a free counterpart for every analysis type. All share the same
GDS-on-process-stack contract. gmsh is pip-installable and runs locally; the
FEM/parasitic solvers generate runnable inputs and execute when their binaries are
present, skipping cleanly otherwise (the same contract as HFSS).

| Backend | Method | Commercial analog | Output | Runs here? |
| --- | --- | --- | --- | --- |
| openEMS | FDTD | HFSS driven-modal | S-params, $Z_0$, $\varepsilon_{\text{eff}}$, E-field | yes |
| Palace | 3D FEM eigenmode | HFSS eigenmode | $f_0$, $Q$, energy, participation | mesh yes / solve via WSL |
| Elmer | electrostatic FEM | Q3D Extractor | capacitance matrix $C_{ij}$ | mesh yes / solve when installed |
| FastHenry | partial-element | Q3D (inductance) | $L$, $R$ | when installed |
| FastCap | BEM panels | Q3D (capacitance) | $C$ matrix | when installed |
| gmsh | mesher | (HFSS mesher) | `.msh` tet mesh | yes |

## gmsh mesh (real, runs here)

`export_mesh` extrudes the GDS layers onto the process stack and tetrahedralizes
them with gmsh (`uv pip install gmsh`). On `readiness_demo` it produced a real mesh
that Palace and Elmer consume:

| Quantity | Value |
| --- | --- |
| Nodes | 3665 |
| Tetrahedra | 13004 |
| Meshed layers | M1, JJ, M2, M3 |
| Mesh file | `.msh` (v2.2), ~0.8 MB |

## Palace eigenmode (HFSS-eigenmode analog)

Palace solves the generalized Maxwell FEM eigenproblem $(K-\omega^2 M)\,x=0$ for the
modal frequency, quality factor $Q=\omega_0 U/P_{\text{loss}}$, and dielectric
participation $p_i=U_i/U_{\text{tot}}$ - the eigenmode quantities openEMS cannot
provide. `export_palace_project` writes a Palace JSON config plus the real gmsh mesh
and returns `status: prepared` (Palace itself solves under WSL/Linux+MPI):

```powershell
py -3 -m uv run python -c "from text_to_gds.server import export_palace_project; print(export_palace_project('workspace/artifacts/readiness_demo.gds', sidecar_path='workspace/artifacts/readiness_demo.sidecar.json', output_name='readiness_demo', target_frequency_ghz=5.0))"
```

## Elmer capacitance (Q3D analog)

Elmer's electrostatic solver evaluates $\nabla\cdot(\varepsilon\nabla\varphi)=0$ and
returns the Maxwell capacitance matrix $C_{ij}=Q_i/V_j$ with stored energy
$W=\tfrac12\sum_{ij}C_{ij}V_iV_j$. `export_elmer_project` writes a `.sif` deck
(one capacitance body per metal) plus the gmsh mesh; `ElmerSolver` populates
`CapacitanceMatrix.dat` when installed.

## FastHenry / FastCap parasitics

FastHenry partitions a conductor into segments and returns $Z=R+j\omega L$ with the
partial inductance $L=\frac{\mu_0 l}{2\pi}\left[\ln\frac{2l}{r}-0.75\right]$; FastCap
solves the BEM panel system $q=P^{-1}\varphi$ for the capacitance matrix.
`export_fasthenry` and `export_fastcap` write the decks (`.inp`, `.lst` + `.qui`
panels) and parse results when the FastFieldSolvers binaries are on PATH.

## Routing

`recommend_em_solver` orders backends by device geometry. A CPW resonator ranks
Sonnet > openEMS > Palace > HFSS > Elmer; a package model puts HFSS and Palace
first. Any backend can run any structure - the order is typical suitability only.

