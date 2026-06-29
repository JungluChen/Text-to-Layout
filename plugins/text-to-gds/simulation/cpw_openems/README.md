# CPW openEMS

The current CPW geometry is not benchmark-ready because it lacks explicit RF and ground-reference ports. `generate_openems_model.py` therefore blocks by default instead of inventing ports.

Once the DSL contains verified port semantics, openEMS can provide Z0, S11, S21, and effective permittivity. Use `postprocess_sparameters.py` only on a real non-empty Touchstone file. Install openEMS from [openEMS](https://www.openems.de/) and scikit-rf for post-processing.
