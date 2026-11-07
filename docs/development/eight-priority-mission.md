# MISSION SPECIFICATION: SYSTEMATIC RESOLUTION OF 8 CRITICAL TASKS & DOCKERIZATION

You are the Principal EDA Architect, Quantum Device Physicist, and Systems Engineer on `Text-to-Layout`.

### Core Engineering Invariants
1. **Deterministic Geometry & DSL Separation:** All natural-language requests translate into typed Pydantic v2 DSL schemas (`textlayout.schema`). Pure Python, `gdsfactory`, and `kfactory` own deterministic polygon generation.
2. **Honest Evidence Contract:** Never fake or assume simulation convergence. Maintain the status hierarchy: `GEOMETRY_PASS`, `ANALYTICAL_ONLY`, `SIMULATION_INPUT_PREPARED`, `SKIPPED_SOLVER_ABSENT`, `SIMULATION_EXECUTED`, `NUMERICALLY_CONVERGED`, and `NOT_FABRICATION_READY`.
3. **Decoupled Engine Core:** Native C++/Fortran/MPI binaries stay isolated in `.tools/` or `$HOME/.cache/textlayout-*`, built with pinned SHA-256 hashes without contaminating repository sources or wheels.
4. **All-in-One Containerization:** The end deliverable must include a multi-stage Docker environment ensuring that any developer can run verified geometries and real solver-backed simulations out of the box with zero host setup friction.

---

### Core Objectives & 8 Critical Priorities

Execute and verify the following 8 priority tasks systematically:

#### Priority 1: Verified Palace 0.17.0 Native / Linux Environment
- Audit and harden `scripts/external/install_palace.py` and `scripts/external/run_palace_smoke.py`.
- Ensure traceable executable provenance in `.tools/palace/install.json` (version, binary path, binary SHA-256).
- Run the official resonant cavity smoke test twice consecutively. Verify both runs succeed, produce parseable `eig.csv`, and exhibit frequency drift $< 10^{-6}$.

#### Priority 2: Atomic Checkpoint & Resume Engine for Palace
- In `src/textlayout/simulation/backends/palace.py`, implement an atomic state-machine manifest:
  `STATE: PENDING | RUNNING_BASE | RUNNING_AMR | CONVERGED | INTERRUPTED`.
- Verify true `base_mesh` $\rightarrow$ `base_amr` checkpoint continuation.
- Ensure that completed runs are never re-executed, interrupted runs preserve their checkpoint artifacts without overwriting earlier progress, and atomic state metadata is written to `manifest.json`.

#### Priority 3: openEMS Port Mesh Snapping & Zero-Signal Rectification
- Diagnose the root cause of zero-signal excitation: FDTD Yee cells collapsing port terminals onto identical mesh lines.
- Implement an automated `MeshSnappingGuard` in the openEMS generator ensuring that CPW signal-to-ground excitation gaps span at least 3 distinct Yee grid lines.
- Verify on a standard 50-ohm CPW through-line: assert non-zero injected port energy, finite real and imaginary S-parameters across all frequency points, and zero non-finite (NaN/Inf) samples.

#### Priority 4: Modal Overlap Tracking & Spatial S-Parameter Verification in Palace
- Address mode swapping across mesh refinement: sorting by frequency alone is insufficient.
- Implement a modal tracking heuristic in `src/textlayout/simulation/backends/palace.py` using field overlap integrals / dot products across successive mesh stages to trace the target physical mode across at least 3 mesh density tiers.
- Enforce that AMR convergence criteria verify eigenvalue stability ($\Delta f / f_0 < 0.1\%$) specifically on the tracked physical mode.

#### Priority 5: Independent Cross-Solver EM Baseline Verification
- Establish a reproducible cross-solver benchmark in `benchmarks/cross_validation/`:
  - Geometry: Standard 50-ohm Coplanar Waveguide (CPW) on high-resistivity silicon.
  - Quasi-static capacitance ($C'$): FasterCap BEM result vs. scikit-rf analytical Ghione/Naldi model (assert error $\le 1.0\%$).
  - High-frequency phase velocity and impedance: openEMS FDTD Touchstone result vs. Palace driven-mode FEM.
- Document quantifiable discrepancies and attribute them strictly to numerical discretization (FDTD Yee grid vs. FEM tetrahedral mesh).

#### Priority 6: Reproducible Multi-Stage Dockerfile & Doctor 3.0 Audit
- Create a multi-stage `Dockerfile` (`ubuntu:24.04` base):
  - `builder`: Pinned builds of Palace (via Spack/CMake), Gmsh 4.15.2, FasterCap, FastHenry2, JoSIM, and openEMS.
  - `runtime`: Minimal runtime libraries, KLayout (headless), Python 3.12, `uv`, and `textlayout`.
- Enhance `textlayout doctor` to output a unified audit table listing `INSTALLED`, `EXECUTABLE`, and `VERIFIED` statuses for every tool.

#### Priority 7: FastHenry2 & FasterCap Ground-Truth Validation
- Build rigorous verification suites in `tests/textlayout_suite/test_field_solvers.py`:
  - FasterCap: Standard parallel-plate capacitor and 22-finger IDC against analytical Bahl/Alley formulas with explicit scaling ($1\,\mu\text{m} \leftrightarrow 10^{-6}\,\text{m}$).
  - FastHenry2: Single-turn planar loop and 4-turn square spiral against Mohan/Wheeler formulas.
- Assert mesh convergence and document operational limits in `docs/verification/solvers.md`.

#### Priority 8: Full Energy-Participation-Ratio (EPR) to Circuit Hamiltonian Chain
- Connect the field-to-qubit pipeline:
  `GDS` $\rightarrow$ `Gmsh 3D Mesh` $\rightarrow$ `Palace Eigenmode` $\rightarrow$ `domain-E.csv` $\rightarrow$ `quantum/epr.py` $\rightarrow$ `scqubits`.
- Extract electric/magnetic field distributions, calculate junction participation $p_{mj}$, compute charging energy $E_C$, Josephson energy $E_J$, qubit frequency $f_{01}$, and anharmonicity $\alpha$.
- Validate against analytical limits: verify that $\alpha \approx -E_C$ in the transmon regime ($E_J/E_C \gg 1$) and compare against `scqubits` exact numerical diagonalization (assert frequency agreement within $0.5\%$).
- Save output to `quantum_analysis.json` and embed a markdown evidence section into `report.md`.

---

### Verification, Quality Gates & Git Workflow

Execute the following verification steps in sequence:
1. `uv run ruff check . --fix`
2. `uv run ruff format .`
3. `uv run mypy --strict src/textlayout`
4. `uv run pytest tests/textlayout_suite`
5. `uv run python scripts/validate_readme_claims.py`
6. `docker build -t textlayout:latest .` (or test build via `docker buildx build`)

When all verification passes:
1. Stage the modified and new files:
   `git add pyproject.toml uv.lock Dockerfile src/ tests/ scripts/ docs/ benchmarks/ to\ do\ list.md`
2. Create a clean, conventional git commit:
   `git commit -m "feat(core): implement 8 critical EDA milestones, Docker runtime, and EPR chain"`
3. Push the commit to the active remote branch:
   `git push origin HEAD`

Begin by inspecting the workspace status, verify the test baseline, and proceed through Priorities 1 through 8.

## Execution interpretation and evidence boundaries

Owner host: Apple Silicon; container target linux/amd64. Execute priorities in
order, retaining current uncommitted work. Priority 6 supersedes the draft
Debian research image as the eventual deliverable: a multi-stage Ubuntu 24.04
builder/runtime with actual pinned solver installations. The research image
is an environment diagnostic, not completion of the all-in-one solver runtime.

Smoke drift is interpreted as relative frequency drift < 1e-6, under identical
inputs, mode count and binary identity. Independent cross-solver discrepancies
cannot be attributed exclusively to discretization until geometry, materials,
boundaries, dimensional approximations and excitation have been controlled.
Analytical expressions have validity ranges; failed comparisons must remain
failed rather than adjusting models or tolerances after observing results.
All eight milestones remain pending until their real execution evidence passes.
