# References

Sources for the analytical models and open-source solvers used in this project.

> **Critical distinction.** A paper citation supports the **analytical method**
> (the closed-form equation used to compute a starting value). It does **not**
> prove that a specific generated geometry meets its target. Only a real solver
> result or a physical measurement can establish that. Every benchmark therefore
> labels analytical results as `ANALYTICAL ONLY` until a solver-owned artifact
> exists.

Full per-benchmark citations also appear inline in each
`examples/benchmarks/*/evidence.md`. Bibliographic locators (journal, volume,
pages, year) are stable identifiers; DOIs are listed only where verified to avoid
fabricated links.

## Analytical models

### Interdigital capacitor (IDC)
- **I. J. Bahl**, *Lumped Elements for RF and Microwave Circuits*, Artech House,
  2003, Ch. 2.
  - Supports: closed-form quasi-static interdigital capacitance used for the IDC
    starting value.
  - Does not prove: the extracted capacitance of the generated geometry.
- **G. D. Alley**, "Interdigital Capacitors and Their Application to
  Lumped-Element Microwave Integrated Circuits," *IEEE Trans. Microwave Theory
  Tech.* **MTT-18**(12), 1028–1033 (1970).
  - Supports: original per-finger capacitance coefficients.
- **S. S. Gevorgian et al.**, "CAD models for multilayered substrate interdigital
  capacitors," *IEEE Trans. Microwave Theory Tech.* **44**(6), 896–904 (1996).
  - Supports: more accurate multilayer/finite-thickness model for EM cross-check.

### Coplanar waveguide (CPW)
- **R. N. Simons**, *Coplanar Waveguide Circuits, Components, and Systems*,
  Wiley, 2001.
  - Supports: conformal-mapping CPW characteristic-impedance model.
- **W. Hilberg**, "From Approximations to Exact Relations for Characteristic
  Impedances," *IEEE Trans. Microwave Theory Tech.* **MTT-17**(5), 259–265 (1969).
  - Supports: closed-form K(k)/K(k′) ratio used in the CPW conformal map.
- **D. M. Pozar**, *Microwave Engineering*, 4th ed., Wiley, 2012.
  - Supports: transmission-line, λ/4 resonator, and LCR resonance theory.

### Spiral inductor
- **S. S. Mohan, M. del Mar Hershenson, S. P. Boyd, T. H. Lee**, "Simple Accurate
  Expressions for Planar Spiral Inductances," *IEEE J. Solid-State Circuits*
  **34**(10), 1419–1424 (1999). DOI: 10.1109/4.792620.
  - Supports: modified-Wheeler and current-sheet inductance expressions.
  - Does not prove: Q-factor or self-resonant frequency of the generated spiral.
- **H. A. Wheeler**, "Simple Inductance Formulas for Radio Coils," *Proc. IRE*
  **16**(10), 1398–1400 (1928).
  - Supports: original Wheeler inductance approximation.

### Quarter-wave resonator
- Uses the Simons/Hilberg CPW model (above) for line impedance and
  **Pozar** (above) for λ/4 = v_p/(4 f0) resonance length.
  - Does not prove: loaded/unloaded Q or coupling, which require EM extraction.

### SQUID / Josephson junction
- **J. Clarke & A. I. Braginski (eds.)**, *The SQUID Handbook*, Vol. 1, Wiley, 2004.
- **M. Tinkham**, *Introduction to Superconductivity*, 2nd ed., Dover, 2004.
  - Support: flux quantization and the Josephson relations.
  - Do not prove: device behavior of the generic, non-foundry-qualified junction
    placeholders in the SQUID benchmark.

### LC resonance (5 MHz feasibility benchmark)
- **D. M. Pozar**, *Microwave Engineering*, 4th ed., Wiley, 2012, Ch. 6 — lumped
  LCR resonance `f0 = 1/(2π√LC)`.
  - Supports: the *required* LC product for a target frequency.
  - Does not prove: that any on-chip geometry realizes the required L and C; the
    benchmark concludes the 5 MHz target is INFEASIBLE on-chip.

## Open-source solvers and tools

| Tool | Use | Canonical source |
|---|---|---|
| FasterCap / FastCap2 | Capacitance extraction (IDC) | https://github.com/ediloren/FasterCap , https://github.com/ediloren/FastCap2 |
| FastHenry / FastHenry2 | Inductance extraction (spiral) | https://github.com/ediloren/FastHenry2 |
| openEMS | FDTD EM (CPW, resonator S-parameters) | https://github.com/thliebig/openEMS |
| Meep | FDTD EM (planned) | https://github.com/NanoComp/meep |
| Elmer FEM | Electrostatic/FEM cross-check (planned) | https://github.com/ElmerCSC/elmerfem |
| scikit-rf | Touchstone / S-parameter post-processing | https://github.com/scikit-rf/scikit-rf |
| gdsfactory | Component model, GDSII lowering | https://github.com/gdsfactory/gdsfactory |
| KLayout | GDS read-back, DRC | https://github.com/KLayout/klayout |

These tools, when actually executed, produce solver-owned artifacts that can
upgrade a benchmark from `ANALYTICAL ONLY` to `SIMULATION EXECUTED`. A prepared
input file alone does not.
