# Lessons from Text-to-CAD

This study used the local `earthtojake/text-to-cad` checkout: its root README, benchmark pages, `skills/cad`, `skills/cad-viewer`, plugin manifest, and repository structure.

## What makes it understandable quickly

- The README begins with a full-width demo and a one-sentence product definition.
- A compact skills table maps each capability to its source.
- Installation is one command for skills, with separate provider-native plugin commands.
- A benchmark gallery puts target, complete prompt, and rendered output in one row.
- Each benchmark links to a page containing the full prompt and objective geometric test cases.
- Skills are self-contained: instructions, progressive references, deterministic scripts, and viewer assets travel together.
- Local preview is a required handoff, not optional decoration.
- Primary and secondary artifacts are explicit: STEP is primary; derived mesh/view formats are secondary.

## What Text-to-Layout adopts

| Text-to-CAD pattern | Text-to-Layout implementation |
| - | - |
| Immediate visual proof | README benchmark table with actual generated PNG/SVG |
| Full prompt per benchmark | `examples/benchmarks/*/prompt.md` |
| Objective benchmark tests | `verification.json` with measured values and limits |
| Primary artifact discipline | GDS is primary; SVG/PNG are previews; JSON is provenance |
| Reproducible scripts | `scripts/generate_benchmarks.py` |
| Self-contained agent procedures | Four focused skills under `skills/` |
| Local tool integration | FastAPI/OpenAPI server plus CLI |

## What must differ for IC layout

Mechanical visual validity is insufficient for RF/IC layout. A layout candidate also needs process-layer mapping, minimum width/spacing, electrical and ground-reference ports, substrate and metal-stack assumptions, parasitic limits, extraction planning, and solver provenance.

Text-to-Layout therefore separates these statuses:

- `analytical`: equation-backed starting estimate;
- `planned`: documented simulation that did not run;
- `executed`: real solver run with a non-empty solver-owned artifact;
- `verified`: deterministic checks passed for the evidence actually available.

A PASS in the README means the listed geometry and artifact checks ran. It does not mean fabrication signoff or EM agreement.
