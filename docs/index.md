# Text-to-Layout

Text-to-Layout is a local-first, evidence-driven cQED layout and simulation
platform. The supported `textlayout` product path turns a natural-language
request into typed design intent, deterministic geometry, verified GDS, and
honest simulation evidence without cloud solver dependencies.

Start with:

- [Architecture](ARCHITECTURE.md) for product boundaries and data flow.
- [Evidence model](evidence_model.md) for canonical status and provenance.
- [Signoff levels](signoff_levels.md) for the Level 0–6 contract.
- [Simulation tools](simulation_tools.md) for optional local solver setup.
- [Reproducibility](reproducibility.md) for deterministic execution policy.
- [Reproduce before edit](development/reproduce_before_edit.md) for the
  mandatory diagnostic workflow used in this repository.

Current execution state is recorded separately in platform reports and
canonical evidence. Documentation never upgrades an absent, skipped, invalid,
or unconverged solver run into an executed claim.
