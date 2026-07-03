# Simulation Plan - TestStructure

- Status: **planned**
- Simulation readiness: **Level 1 - geometry/research workflow defined**
- No solver result is claimed by this file.

## Recommended extraction

- **capacitance:** FasterCap/FastCap on the embedded IDC region (documented extraction region).
- **transitions:** Full-wave EM (openEMS/HFSS/Sonnet) for launch and step transitions — not performed here.

## Comparison method

1. Execute the named solver and retain its input, version, log, and output artifact.
2. Extract the requested physical quantity from the solver-owned output.
3. Compare it with the Layout DSL target and state the error and tolerance.
4. Change Layout DSL parameters, regenerate, and rerun verification.

## Limitations

- The capacitance model covers the IDC region only; launch pads and feed traces add parasitic shunt capacitance that a real measurement must de-embed.
- The CPW feed impedance is an analytical estimate; no EM solver validates the launch-to-feed and feed-to-IDC transitions.
- No radiation, substrate loss, or self-resonance model is included.
