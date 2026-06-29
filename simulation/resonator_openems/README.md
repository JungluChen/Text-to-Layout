# Resonator openEMS

The benchmark defines a capacitively coupled open end, grounded short, feedline, and explicit ground-reference ports. `generate_openems_model.py` verifies that geometry and writes the openEMS input manifest.

The analytical `L=vp/(4f)` length remains an initial value. A Level 3 result requires a meshed openEMS run, Touchstone output, and resonance/Q extraction.
