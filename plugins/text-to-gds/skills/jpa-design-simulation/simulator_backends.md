# Simulator Backends

Select backends by physical question. Discovery or input preparation is not execution evidence.

## FasterCap / FastCap

- Role: geometry-level electrostatic capacitance extraction.
- Primary JPA use: extract IDC capacitance and capacitance matrices from conductor geometry plus dielectric definitions.
- Required inputs: geometry derived from the verified layout, conductor/net mapping, units, dielectric stack, meshing/discretization controls, and source-layout hash.
- Required evidence: executable/version, real command, logs, non-empty native output, parsed units, and conductor mapping.
- Boundary: not a transient circuit simulator; it does not prove JPA resonance or gain.

Another electrostatic or EM solver may substitute only when its physical formulation, geometry/material inputs, outputs, and provenance are declared. Record the actual backend rather than labeling it FasterCap/FastCap.

## JoSIM

- Role: superconducting circuit transient simulation.
- Primary JPA use: LC/JJ/SQUID/JPA circuit checks using explicit lumped parameters, flux bias, sources, and probes.
- Valid outputs: parsed transient quantities and resonance or pump/signal/idler metrics supported by the deck and run.
- Boundary: not an IDC capacitance extractor. A capacitor value in a JoSIM deck is an input and cannot prove the physical layout's capacitance.

## PSCAN2

- Role: optional superconducting circuit transient simulation.
- Primary JPA use: JJ/SQUID and JTWPA-style transient studies when a supported local installation and deck format are available.
- Valid outputs: parsed real transient data and derived metrics supported by retained artifacts.
- Boundary: not a geometry-level capacitance extractor and not mandatory when unavailable.

## WRspice

- Role: optional SPICE-family circuit simulation with Josephson-junction support.
- Primary JPA use: independent circuit-level transient checks when the installed build supports the required JJ model.
- Valid outputs: parsed real transient or sweep data and metrics supported by the run.
- Boundary: not a geometry-level capacitance extractor. Confirm actual JJ-model support and version; generic SPICE availability alone is insufficient.

## Common execution contract

For every backend:

1. Record discovery result and exact executable.
2. Capture backend version or explicitly report that version detection failed.
3. Retain input files and a run manifest.
4. Invoke a real local subprocess with timeout and return-code handling.
5. Retain stdout, stderr, command, return code, and non-empty native outputs.
6. Parse only documented outputs and validate units and run identity.
7. Use `SKIPPED_SOLVER_ABSENT` when optional software is unavailable.
8. Use `FAILED` for attempted runs with nonzero exit, timeout, missing/empty outputs, or parse failure.

Do not claim agreement by comparing simulators that share only the same assumed lumped parameters while the geometry-level quantity remains unextracted. State the independence and limitations of each comparison.
