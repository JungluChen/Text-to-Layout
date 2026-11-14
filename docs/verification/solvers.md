# FasterCap and FastHenry2 validation status

## FasterCap Status
**Status: analytical references and prepared geometry only. Numerical solver
agreement and convergence are pending.** The former 4% / 1.8% FasterCap claims
came from hard-coded scaling of analytical formulas in
`tests/textlayout_suite/test_field_solvers.py`; they were not solver outputs and
are withdrawn.

For FasterCap, prepare a valid multi-conductor CPW and parallel-plate case,
retain the binary version/hash, solver-owned capacitance matrix and logs, and
repeat at three panel resolutions. Compare compatible capacitance definitions
with a separately sourced analytical or published reference under predefined
error and convergence limits.

## FastHenry2 Status
**Status: native solver executed; numerical convergence and independent validation pending (`fasthenry 3.0.1`).**
The full real execution evidence packet is recorded in:
- JSON evidence: `docs/verification/evidence/fasthenry_real_run.json`
- Markdown report: `docs/verification/evidence/fasthenry_real_run.md`

### Verification Summary
- **Binary provenance:** `.tools/FastHenry2/bin/fasthenry`, Mach-O 64-bit arm64, SHA-256: `007a93526fa931ecea0e86fe37eb43a9b5b88523325c644072fec6392563c3ce`.
- **Single-Turn Planar Loop (100 µm × 100 µm, w = 4 µm, t = 0.2 µm):**
  - Real FastHenry PEEC result: $L = 0.3091\,\text{nH}$ ($309.06\,\text{pH}$ at 1 MHz).
  - Grover (1946) analytical formula: $L = 0.3123\,\text{nH}$ ($312.31\,\text{pH}$).
  - Relative discrepancy: **1.031%**.
- **4-Turn Square Spiral Inductor ($D_{\text{out}} = 150\,\mu\text{m}, w = 4\,\mu\text{m}, s = 4\,\mu\text{m}, t = 0.2\,\mu\text{m}$):**
  - Real FastHenry PEEC result: $L = 3.2570\,\text{nH}$ at `nwinc=4`.
  - Mohan Current Sheet formula: $L = 3.5008\,\text{nH}$ (discrepancy: **6.964%**).
  - Mohan Modified Wheeler formula: $L = 3.5189\,\text{nH}$ (discrepancy: **7.444%**).
  - Width filament changes (`nwinc = 1, 2, 4`) gave successive $\Delta L$ of -0.0517% and -0.0410%. Height filaments, segment length and frequency were not refined; no convergence tolerance was predefined.
- **Evidence scope:** The rerun packet retains each input deck, output matrix text, hashes and complete process logs. Grover and Mohan are analytical estimates, not independent measurements for this exact geometry. Normal-metal conductivity was used ($\sigma = 5.8 \times 10^7\,\text{S/m}$); kinetic inductance is not inferred from classical PEEC.
