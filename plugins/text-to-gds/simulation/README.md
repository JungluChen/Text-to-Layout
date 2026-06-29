# Simulation Workflow

> **Status:** documentation only. The plugin generates and verifies layout
> geometry today; EM extraction is a documented *manual* workflow plus an
> AI-assisted optimization loop. No solver is auto-driven yet — and the tool
> never reports a simulated value it did not actually compute.

The generated GDSII is the hand-off point into electromagnetic (EM) extraction.

```
Generated GDS
     │
     ▼
Import to HFSS / Q3D / ADS
     │
     ▼
Assign material, substrate, ports, boundaries
     │
     ▼
EM extraction  ──►  C, L, Q, S-parameters, resonance frequency
     │
     ▼
Compare with target
     │
     ▼
AI optimization loop  ──►  adjust Layout DSL parameters  ──►  regenerate
     │
     ▼
Report
```

## Where each solver fits

| Quantity | Recommended solver | Workflow |
|---|---|---|
| Capacitance matrix (C) | **Q3D Extractor** | [`q3d_workflow.md`](q3d_workflow.md) |
| S-parameters, resonance, Q | **HFSS** (full-wave FEM) | [`hfss_workflow.md`](hfss_workflow.md) |
| Circuit-level S-params, harmonic balance | **ADS** | [`ads_workflow.md`](ads_workflow.md) |
| Planar EM, capacitance, self-resonance | **Sonnet** | [`sonnet_workflow.md`](sonnet_workflow.md) |

## The optimization loop (target-driven)

1. Generate a candidate layout from a Layout DSL (e.g. IDC at `finger_pairs=24`).
2. Extract the figure of merit (e.g. capacitance) in Q3D/HFSS.
3. Compare to the target (e.g. 0.6 pF).
4. If outside tolerance, adjust DSL parameters (more/fewer fingers, longer
   overlap) and regenerate — the deterministic engine guarantees the new layout
   still passes design-rule verification before re-simulation.
5. Repeat until convergence; emit a report with full provenance.

The analytical capacitance in `IDC` metadata
(`capacitance_method: bahl_alley_quasi_static`) is only a
*starting point* for step 1 — it must be replaced by an EM-extracted value
before any performance claim.

## Honesty contract

Following the project's truth principle (and Text-to-CAD's "report only checks
that actually ran"): a value is reported as **simulated** only when a real solver
produced it. Until then it is labelled `estimated`/`analytical` with an explicit
low confidence.
