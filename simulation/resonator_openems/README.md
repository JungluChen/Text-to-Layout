# Resonator openEMS

The benchmark defines a capacitively coupled open end, grounded short, feedline, and explicit ground-reference ports. `generate_openems_model.py` verifies that geometry and writes the openEMS input manifest.

The analytical `L=vp/(4f)` length remains an initial value. A Level 3 result requires a meshed openEMS run, Touchstone output, and resonance/Q extraction.


The wrapper calls `simulate_layout`: when a runnable stack is available it may
execute the solver, so it is not a preparation-only command. Use a fresh output
directory and inspect existing jobs before running it.

The retained showcase05 failure used older inputs whose six-micrometre ports
collapsed to zero-dimensional grid points. Current generation includes the port
endpoint mesh lines, but prepared inputs alone do not validate that correction.
See the [artifact audit](../../docs/progress/2026-11-06-222005.md) and
[scientific-result guide](../../docs/guidebook/scientific-result-check.md).
Never regenerate over the retained failed packet or claim a resonance from its
all-non-finite Touchstone data.
