# CPW analytical reference and pending cross-solver benchmark

`compute_analytical_ghione_naldi` evaluates a 10 µm center, 6.5 µm gap CPW
reference on εr = 11.7 silicon. It uses scikit-rf when installed and a local
conformal-mapping implementation otherwise. This is an **analytical estimate**;
it does not establish the actual capacitance or impedance of a fabricated line.

The former FasterCap, openEMS and Palace numbers in this directory were made by
multiplying that analytical result by fixed factors. No solver was invoked. Those
numbers and the former 0.42% / 0.30% agreement claims are withdrawn.
`compute_fastercap_bem_capacitance`,
`compute_high_frequency_cross_validation`, and
`run_cpw_cross_validation_benchmark` now raise `NotImplementedError` until
solver-owned outputs are connected.

To accept a numerical comparison, run the same versioned geometry, materials,
boundary conditions and frequency band through each solver. Retain inputs,
binary identity and SHA-256, raw outputs, logs, convergence tiers, units and
parsing code. Establish tolerances before examining final results. Compare only
compatible observables, then generate a report from those retained records.
The real openEMS resonator case currently has non-finite samples and Palace
diagnostics remain pending; neither is a valid CPW reference here.
