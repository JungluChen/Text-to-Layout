---
name: text-to-gds-signoff
description: "Review Text-to-GDS generated artifacts for local signoff readiness: DRC reports, process-rule fallbacks, sidecar completeness, simulation status, scientific plots/data, CAD exports, 3D preview, plugin bundle validation, and remaining tapeout risks. Use when the user asks to verify, audit, prepare release, or decide whether a layout/simulation result is trustworthy."
---

# Text-to-GDS Signoff Review

Use this skill to audit evidence after layout and simulation tools run.

## Checklist

- Confirm `.gds`, `.layout.png`, `.sidecar.json`, `.drc.json`,
  `.extraction.json`, `.magic.json`, `.stack3d.html`, `.simulation.json`, and
  `.simulation.png` exist where expected.
- Confirm `.scientific.png`, `.scientific.svg`, `.scientific.csv`,
  `.layout.svg`, `.layout.dxf`, `.stack.stl`, and `.cad.json` exist when the
  workflow requested scientific review or CAD/interchange outputs.
- Confirm `.validation.json` exists when the user asks about the academic or
  industrial validation roadmap.
- Check DRC status and whether it came from external KLayout or fallback rules.
- Check Magic status, generated TCL, SPICE output presence, and whether a real
  process tech file was supplied.
- Check simulator adapter status and whether the external tool executed.
- Check `physical_performance.flux_tuning` for LJPA/SQUID designs and confirm
  flux bias, SQUID asymmetry, tuned `Ic/Lj/f0`, and coil-current period were
  recorded when requested.
- Inspect sidecar ports, layer names, device metadata, and process assumptions.
- Run repository checks before release: compileall, Ruff, pytest, scaffold
  validation, plugin validation, and `git diff --check`.

## Guardrails

- Treat fallback DRC, starter circuit models, local plots, sweeps, and
  CAD-style derived solids as iteration gates, not foundry signoff.
- Report unresolved risks directly.
