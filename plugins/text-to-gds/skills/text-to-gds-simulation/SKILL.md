---
name: text-to-gds-simulation
description: "Run and interpret local Text-to-GDS circuit simulations, including ideal JJ calculations, Aharonov-Bohm dc-SQUID flux tuning, JosephsonCircuits.jl harmonic balance, JoSIM transient decks, ngspice starter decks, simulation plot PNGs, and future PySpice handoff. Use when the user asks for Ic, Lj, S-parameters, gain, bandwidth, flux tuning, transient behavior, simulation plots, or simulator adapter setup for superconducting or IC layouts."
---

# Text-to-GDS Simulation

Use this skill for local circuit analysis after a Text-to-GDS sidecar exists.
Keep claims tied to actual adapter status and generated files.

## Workflow

1. Start from a `.sidecar.json`; compile a registered PCell first if needed.
2. Run `extract_layout` when geometry, ports, or layer data need to be explicit.
3. Run `run_simulation`:
   - `simulator="mock_jj"` for deterministic ideal `Ic` and `Lj`.
   - `simulator="JosephsonCircuits.jl"` with `analysis_mode="auto"` for LJPA
     S-parameter harmonic balance or JJ single-port reflection fallback.
   - `simulator="josim"` for a transient starter deck when JoSIM is installed.
   - `simulator="ngspice"` for a linearized JJ transient deck or LJPA
     small-signal two-port RLC starter when ngspice is installed.
   - For LJPA/SQUID flux tuning, pass `flux_bias_phi0`, `squid_asymmetry`,
     and either `flux_period_current_ma` or `flux_mutual_inductance_ph`.
4. Return `.simulation.json`, `.simulation.png`, `.scientific.png`,
   `.scientific.svg`, `.scientific.csv`, adapter status,
   `physical_performance`, input/output ports, and the main numerical results
   such as `Ic`, `Lj`, gain, bandwidth, loaded Q, saturation/P1dB, and parsed
   adapter row counts.
5. Use `export_scientific_plot` when a saved simulation JSON needs a regenerated
   publication-style plot/data package.
6. Use `run_parameter_sweep` for local sensitivity studies across `Jc`,
   junction area, target frequency, bandwidth, pump current, coupling
   capacitance, resonator capacitance, shunt capacitance, flux bias, or SQUID
   asymmetry.

## Guardrails

- Do not say JosephsonCircuits.jl, JoSIM, ngspice, PySpice, or Magic ran unless
  the adapter status proves execution.
- Treat Magic VLSI `executed_with_warnings` as a real run with process-tech
  limitations. Do not call it calibrated extraction unless a process-specific
  Magic tech file was used.
- Treat PySpice entries as discovery/roadmap adapters until execution support
  is implemented.
- Treat ngspice starter decks as circuit-iteration models, not extracted SPICE
  signoff.
- Treat generated plots and sweeps as local iteration evidence, not signoff.
