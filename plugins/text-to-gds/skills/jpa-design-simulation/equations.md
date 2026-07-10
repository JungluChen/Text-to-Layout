# First-Principles Equations

Use SI units in calculations and preserve user-facing units in reports. Store each input value, unit, source, equation identifier, result, and assumption in `design_equations.json`.

## Flux quantum

```text
Phi0 = 2.067833848e-15 Wb
```

Use this declared constant consistently. Do not silently substitute a rounded value.

## LC resonance

```text
f0 = 1 / (2*pi*sqrt(L*C))
```

This is the ideal lumped, linear resonance. `L` is total small-signal inductance and `C` is total effective capacitance, including declared stray terms.

## Required capacitance

```text
C = 1 / ((2*pi*f0)^2 * L)
```

Use when frequency and an independently justified total inductance are known. This produces an analytical target, not geometry-extracted IDC capacitance.

## Required inductance

```text
L = 1 / ((2*pi*f0)^2 * C)
```

Use when frequency and an independently justified total capacitance are known. State whether the result includes SQUID, geometric, kinetic, and stray inductance.

## Loaded Q

```text
Q_loaded = f0 / BW
```

Assume the bandwidth definition is compatible with the resonator model, normally a small-signal 3 dB bandwidth. This relation does not separate internal and coupling Q and does not establish gain bandwidth under pumping.

## Basic Josephson inductance

```text
LJ0 = Phi0 / (2*pi*Ic)
```

Treat `Ic` as the declared effective critical current for the modeled element. State whether it is per junction or the effective SQUID critical current. This is a zero-bias, small-signal approximation.

## SQUID tunability

```text
LJ(phi) = LJ0 / abs(cos(pi*phi/phi0))
```

Use for an ideal symmetric, negligible-loop-inductance SQUID with identical junctions. Define `phi0 = Phi0` in machine-readable data. Do not evaluate at or too near half-integer flux quanta; declare a numerical and physical exclusion margin. Junction asymmetry, screening, loop inductance, bias current, and nonlinear drive modify this relation.

## Frequency tuning

```text
f(phi) = 1 / (2*pi*sqrt((L_stray + LJ(phi))*C))
```

Use a consistent capacitance and include all declared series/effective stray inductance. This is a small-signal lumped estimate. It does not predict pumped gain, saturation, noise, distributed modes, or fabrication variation.

## Required assumptions and limitations

- State the topology and whether L/C are total effective values or component-only values.
- State substrate, dielectric, film, junction, loss, coupling, and temperature assumptions when used.
- Treat IDC formulas and the equations above as analytical initialization and sanity checks.
- Require electrostatic/EM extraction for physical IDC capacitance.
- Require circuit simulation with a suitable nonlinear pump/signal model for gain-related claims.
- Check lumped-element validity, self-resonance, parasitics, flux singularity proximity, and feasible process dimensions.
- Carry uncertainty or parameter ranges when process values are not fixed.
