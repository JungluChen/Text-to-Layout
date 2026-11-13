# Palace 0.17.0 Smoke Repeatability & Dual-Mesh Audit (P1 Verification)

## 1. CI Run & Provenance
- **GitHub Actions Run ID:** [`43432426498`](https://github.com/JungluChen/Text-to-Layout/actions/runs/43432426498) (Job: `131908984951`)
- **Status / Conclusion:** `completed` / `success`
- **Workflow:** `palace-integration.yml`
- **Source Commit:** `f2aaf71f9cfd0c1598b0f803c516f8ef256e297f`
- **Palace Version:** `0.17.0` (commit: `12d8069afb5aa9e169a17e303d735e120968e9f2`)
- **Palace Binary SHA-256:** `ad43ec030f51435f32150a5c72cb324ca03083d2ffc2f91405bbf41c6bc2240f`
- **Gmsh Version:** `4.15.2` (module SHA-256: `f4b0935cebde899750293d87a643090e5ea33c9b18d249267f507db68a0e01c3`)

---

## 2. Dual-Mesh Artifact Verification
Downloaded artifact `palace-pre-benchmark-1` (ID: `14046344969`) containing the mesh files generated in independent directories for Run 1 and Run 2:

| Run Stage | Relative Path | File Size (bytes) | Computed SHA-256 |
| :--- | :--- | :--- | :--- |
| **Run 1 (Smoke)** | `out/toolchain/palace_smoke/mesh/cavity2d.msh` | 451,217 | `4ab22f7051abb00e881a9a098d5dcda082dd1fcfde7784f8c2ff3a7c2a95d6f1` |
| **Run 2 (Repeat)** | `out/toolchain/palace_smoke_repeat/mesh/cavity2d.msh` | 451,217 | `4ab22f7051abb00e881a9a098d5dcda082dd1fcfde7784f8c2ff3a7c2a95d6f1` |

**Mesh Identity Assertion:** `SHA256(Mesh 1) == SHA256(Mesh 2) -> TRUE`

---

## 3. Consecutive Eigenmode Repeatability & Frequency Drift (< $10^{-6}$)
Extracted from `postpro/eigenmode/eig.csv` across both independent runs:

| Mode | Run 1 Frequency (GHz) | Run 2 Frequency (GHz) | Relative Drift | Limit ($< 10^{-6}$) | Status |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | `0.1039343283770` | `0.1039343283770` | **`0.00e+00`** | `1.0e-06` | **PASS** |
| **2** | `0.2078686586235` | `0.2078686586235` | **`0.00e+00`** | `1.0e-06` | **PASS** |
| **3** | `0.2078686591775` | `0.2078686591775` | **`0.00e+00`** | `1.0e-06` | **PASS** |
| **4** | `0.2324042265491` | `0.2324042265491` | **`0.00e+00`** | `1.0e-06` | **PASS** |
| **5** | `0.2939706870914` | `0.2939706870914` | **`0.00e+00`** | `1.0e-06` | **PASS** |

**Repeatability Status:** `REPEATABLE_SMOKE`  
**Max Relative Drift:** `0.00` (Strictly $< 10^{-6}$)  
All 5 eigenmodes exhibit zero numerical drift between the two consecutive Palace executions.

