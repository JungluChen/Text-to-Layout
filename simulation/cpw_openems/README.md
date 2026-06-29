# CPW openEMS

The CPW benchmark has explicit RF and ground-reference ports. `generate_openems_model.py` verifies the Layout DSL and writes an openEMS input manifest containing geometry bounds, substrate assumptions, ports, and expected outputs.

This is Level 2 preparation, not a mesh or result. A Level 3 claim requires an openEMS run, convergence evidence, and non-empty Touchstone output. `postprocess_sparameters.py` accepts only a real Touchstone file.
