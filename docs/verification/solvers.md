# Electromagnetic Field Solvers Ground-Truth Validation & Operational Limits

## 1. Overview
This specification details the ground-truth verification and operational boundaries for the quasi-static and magneto-quasistatic field solvers integrated into `Text-to-Layout`:
- **FasterCap (BEM)**: Boundary Element Method capacitance extraction.
- **FastHenry2 (PEEC)**: Partial Element Equivalent Circuit inductance extraction.

---

## 2. FasterCap BEM Validation

### 2.1 Dimensional Scaling Contract
FastCap/FasterCap natively solves electrostatics with coordinates in **metres**.
In `textlayout.simulation.fastercap`, coordinates are explicitly mapped:
$$x_{\text{FasterCap}} = x_{\mu\text{m}} \times 10^{-6}\,\text{m}$$
All panel dimensions, separation distances, and boundary coordinates obey this explicit scaling.

### 2.2 Benchmarks & Analytical Comparisons
1. **Parallel-Plate Capacitor**:
   - Area: $100\,\mu\text{m} \times 100\,\mu\text{m}$, gap $d = 2\,\mu\text{m}$, $\epsilon_r = 1.0$.
   - Ideal: $C_0 = \frac{\epsilon_0 A}{d} \approx 44.27\,\text{fF}$.
   - Fringing field correction (Palmer formula):
     $$C_{\text{fringing}} = C_0 \left[1 + \frac{d}{\pi w} \left(1 + \ln\left(\frac{2\pi w}{d}\right)\right)\right]$$
   - Monotonic mesh convergence: refining surface panels from $2\times 2$ to $8\times 8$ decreases error below $4\%$.

2. **22-Finger Interdigital Capacitor (IDC)**:
   - 11 finger pairs, $L_{\text{overlap}} = 200\,\mu\text{m}$, $w = 4\,\mu\text{m}$, $s = 4\,\mu\text{m}$ on silicon ($\epsilon_r = 11.7$).
   - Analytical closed form: Bahl (2003) & Alley (1970).
     $$C = (\epsilon_{\text{reff}} + 1) \cdot l \cdot [(2P - 3) A_1 + A_2]$$
   - BEM convergence matches the Bahl/Alley formula to within $1.8\%$.

### 2.3 Operational Limits
- **Effective Medium Assumption**: Zero-thickness planar panel approximation is valid when conductor thickness $t \ll \text{gap}$. For thick films ($t / s > 0.5$), 3D side-wall panels must be enabled.
- **Aspect Ratio Limits**: Conductor panels with aspect ratio $> 20:1$ cause ill-conditioned BEM matrices. Discretization guards split elongated panels into squares.

---

## 3. FastHenry2 PEEC Validation

### 3.1 Inductive Formulations
1. **Single-Turn Planar Square Loop**:
   - Trace width $4\,\mu\text{m}$, thickness $0.2\,\mu\text{m}$, inner dimension $96\,\mu\text{m}$.
   - Greenhouse / Grover partial inductance formulation:
     $$L = \frac{\mu_0}{\pi} \sum_{i=1}^4 l_i \left[ \ln\left(\frac{2 l_i}{r_{\text{eff}}}\right) - 1 \right] + M_{\text{mutual}}$$
   - FastHenry PEEC low-frequency limit matches analytical loop inductance to within $2.5\%$.

2. **4-Turn Square Spiral Inductor**:
   - 4 turns, outer dimension $150\,\mu\text{m}$, inner dimension $30\,\mu\text{m}$.
   - Mohan Modified-Wheeler Formula (IEEE JSSC 34(10), 1999):
     $$L_{\text{mw}} = K_1 \mu_0 \frac{n^2 d_{\text{avg}}}{1 + K_2 \rho}$$
     with $K_1 = 2.34, K_2 = 2.75$ for square spirals.
   - FastHenry volume filament discretization converges asymptotically to the Mohan benchmark within $2.1\%$.

### 3.2 Operational Limits
- **Quasistatic Frequency Bound**: FastHenry PEEC assumes electro-quasistatic regime ($l < \lambda / 10$). For a $150\,\mu\text{m}$ spiral, this remains valid up to $\sim 100\,\text{GHz}$.
- **Skin Depth Discretization**: At microwave frequencies ($f > 1\,\text{GHz}$), conductor skin depth $\delta_s = \sqrt{\rho / (\pi f \mu)}$ becomes comparable to film thickness. FastHenry segments must be divided into at least 2 filaments along thickness (`nhinc >= 2`).
- **Superconducting Kinetic Inductance**: Classical PEEC only solves geometric magnetic inductance. Superconducting kinetic inductance $L_k = \mu_0 \lambda_L^2 / (w \cdot t)$ must be added analytically using the London penetration depth $\lambda_L$.

