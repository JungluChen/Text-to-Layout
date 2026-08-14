# JTWPA numerical-simulation reference boundary

This note records the narrow implementation ideas taken from Levochkina et al.,
[“Simulating the behaviour of travelling wave parametric amplifiers using a
circuit simulator”](https://arxiv.org/abs/2402.12037). It is a literature and
adapter-design reference, not solver-execution evidence.

The supported product code uses the reference for three bounded choices:

- generate separate transient decks for JoSIM, PSCAN2, and WRspice instead of
  assuming their input languages are interchangeable;
- remove the initial propagation transient before estimating steady-state
  spectral amplitudes; and
- keep circuit-simulator results distinct from geometry-level EM extraction.

The implementation hooks are
`src/textlayout/simulation/templates.py` and
`src/textlayout/simulation/postprocess.py`. Their deterministic tests may
exercise parsing and signal-processing logic without claiming a solver ran.

JoSIM, PSCAN2, and WRspice validate circuit behaviour from supplied lumped
parameters. They do not extract capacitance or inductance from GDS geometry,
and their availability or execution cannot by itself establish design-level
physics signoff.
