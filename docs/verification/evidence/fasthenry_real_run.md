# FastHenry2 native execution and analytical comparison

**Date:** `2026-11-14T14:38:13.968059+00:00`
**Solver Binary:** `/Users/ludko/Desktop/text2layout/Text-to-Layout/.tools/FastHenry2/bin/fasthenry`
**Binary SHA-256:** `007a93526fa931ecea0e86fe37eb43a9b5b88523325c644072fec6392563c3ce`
**Banner:** `Running FastHenry 3.0.1 (28May12)`
**Platform:** `Mac (arm64, darwin)`

---

## 1. Planar Single-Turn Loop (100 µm × 100 µm, w = 4 µm, t = 0.2 µm)

- **Analytical Reference (Grover 1946):** `0.3123 nH` (312.31 pH)

| Refinement (`nwinc`) | PID | Runtime (s) | Resistance (Ω) | Reactance (Ω) | FastHenry $L$ (nH) | Error vs Grover (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `nwinc=1` | 29925 | 0.0098 | 8.5345 | 0.001942 | **0.3091** | **1.038%** |
| `nwinc=2` | 29926 | 0.0034 | 8.5345 | 0.001942 | **0.3091** | **1.037%** |
| `nwinc=4` | 29927 | 0.0035 | 8.5345 | 0.001942 | **0.3091** | **1.031%** |

## 2. 4-Turn Square Spiral Inductor (Dout = 150 µm, w = 4 µm, s = 4 µm, t = 0.2 µm)

- **Analytical Reference (Mohan Current Sheet):** `3.5008 nH`
- **Analytical Reference (Mohan Modified Wheeler):** `3.5189 nH`

| Refinement (`nwinc`) | PID | Runtime (s) | Resistance (Ω) | Reactance (Ω) | FastHenry $L$ (nH) | vs Mohan CS (%) | vs Mohan MW (%) | Convergence $\Delta L$ (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `nwinc=1` | 29928 | 0.0046 | 39.9569 | 0.020483 | **3.2600** | 6.878% | 7.358% | **0.0%** |
| `nwinc=2` | 29929 | 0.0044 | 39.9569 | 0.020473 | **3.2583** | 6.926% | 7.406% | **-0.0517%** |
| `nwinc=4` | 29930 | 0.0079 | 39.9569 | 0.020464 | **3.2570** | 6.964% | 7.444% | **-0.041%** |

## 3. Results and limitations

1. **Single-turn Loop:** FastHenry PEEC result `0.3091 nH` differs from the nominal Grover analytical estimate `0.3123 nH` by **1.031%**. The deck geometry and formula dimensions require reconciliation before treating this as reference agreement.
2. **4-turn Spiral:** FastHenry PEEC result `3.2570 nH` differs from the Mohan Current Sheet estimate by **6.964%** and Modified Wheeler by **7.444%**. These are approximate formulas, not an independent same-geometry validation.
3. **Filament refinement observation:** Width filament counts `nwinc = 1, 2, 4` changed the spiral inductance by -0.0517% and -0.0410% between tiers. This does not establish mesh convergence: height filaments, segment length and frequency were not refined, and no tolerance was predefined.
4. **Evidence scope:** These were real native FastHenry executions, with the input decks, deck/output hashes, complete stdout/stderr and Zc.mat text retained in JSON. The Grover and Mohan values are analytical estimates; no independently measured or paper-matched geometry is retained. Numerical validation remains pending.
