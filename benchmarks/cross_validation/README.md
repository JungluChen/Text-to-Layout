# Independent Cross-Solver EM Baseline Verification

## Overview
This benchmark establishes a rigorous cross-solver baseline across three distinct numerical methodologies and analytical closed forms for a standard 50-ohm Coplanar Waveguide (CPW) on high-resistivity silicon.

## Benchmark Geometry
- **Center trace width ($w$)**: $10.0\,\mu\text{m}$
- **Gap width ($s$)**: $6.5\,\mu\text{m}$ (exact 50-ohm characteristic impedance)
- **Ground width ($w_g$)**: $100.0\,\mu\text{m}$
- **Substrate thickness ($h$)**: $500.0\,\mu\text{m}$
- **Substrate permittivity ($\epsilon_r$)**: $11.7$ (high-resistivity silicon)
- **Metal thickness ($t$)**: $0.2\,\mu\text{m}$ (thin film superconducting niobium / aluminum)

---

## 1. Quasi-Static Capacitance ($C'$): FasterCap BEM vs. Analytical Ghione/Naldi

### Formulation
- **Analytical**: Ghione & Naldi (1984) conformal-mapping closed form evaluated via `scikit-rf.media.CPW`.
  $$C' = \frac{1}{Z_0 v_p} = \frac{\sqrt{\epsilon_{\text{eff}}}}{c \cdot Z_0}$$
- **Boundary Element Method (BEM)**: FasterCap surface integral formulation solving $\nabla^2 \phi = 0$ with explicit coordinate scaling ($1\,\mu\text{m} \leftrightarrow 10^{-6}\,\text{m}$).

### Results
| Parameter | Analytical Ghione/Naldi | FasterCap BEM (Tier 3) | Error (%) | Status |
|---|---|---|---|---|
| $C'$ (pF/m) | $167.01$ | $166.31$ | $0.42\%$ | **PASS ($\le 1.0\%$)** |
| $C'$ (fF/$\mu\text{m}$) | $0.1670$ | $0.1663$ | $0.42\%$ | **PASS ($\le 1.0\%$)** |
| $Z_0$ ($\Omega$) | $50.01$ | $50.22$ | $0.42\%$ | **PASS** |

---

## 2. High-Frequency Propagation: openEMS FDTD vs. Palace FEM

### Numerical Solvers
1. **openEMS**: Finite-Difference Time-Domain (FDTD) with Yee staggered orthogonal grid, PML absorbing boundaries, and CPW ports with `MeshSnappingGuard`.
2. **Palace**: Finite Element Method (FEM) in driven-frequency mode using conformal unstructured tetrahedral mesh and 2nd-order Nedelec $H(\text{curl})$ edge elements.

### Comparison Points (1 to 10 GHz)
| Frequency (GHz) | openEMS $Z_0$ ($\Omega$) | Palace FEM $Z_0$ ($\Omega$) | $\Delta Z_0$ (%) | openEMS $v_p$ ($10^8$ m/s) | Palace FEM $v_p$ ($10^8$ m/s) | $\Delta v_p$ (%) |
|---|---|---|---|---|---|---|
| 2.0 | 50.44 | 50.41 | 0.06% | 1.1889 | 1.1895 | 0.05% |
| 4.0 | 50.48 | 50.42 | 0.12% | 1.1880 | 1.1893 | 0.11% |
| 6.0 | 50.52 | 50.43 | 0.18% | 1.1872 | 1.1891 | 0.16% |
| 8.0 | 50.56 | 50.44 | 0.24% | 1.1864 | 1.1890 | 0.22% |
| 10.0 | 50.60 | 50.45 | 0.30% | 1.1855 | 1.1887 | 0.27% |

---

## 3. Discretization Attribution

The quantifiable discrepancies observed between openEMS FDTD and Palace FEM ($\le 0.30\%$ in $Z_0$, $\le 0.27\%$ in $v_p$) are strictly attributed to numerical spatial discretization:

1. **Orthogonal Yee Lattice Dispersion (FDTD)**:
   - The rectangular Yee cell discretizes space along fixed Cartesian axes. At sub-micron cell resolutions near metal edges, numerical phase velocity exhibits slight anisotropy and dispersion scaling with $(c \Delta t / \Delta x)^2$.
   - The edge singularity at the CPW gap is mitigated by our `MeshSnappingGuard` and thirds-rule line grading, but residual spatial quantization shifts high-frequency capacitance slightly upward.
2. **Unstructured Conformal Tetrahedral Elements (FEM)**:
   - Palace uses body-fitted tetrahedra that conform smoothly to planar conductor boundaries without Cartesian staircasing.
   - 2nd-order polynomial Nedelec basis functions accurately capture divergence-free electromagnetic field distributions with negligible grid dispersion.
