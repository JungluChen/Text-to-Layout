# SQuADDS — entry 007 audit

Document class: MANUAL_DOCUMENTATION. Entry remains unchecked.

## Source identity and licenses

Official code repository: https://github.com/LFL-Lab/SQuADDS . Inventory hint
SQuADDS/SQuADDS must not be treated as verified source. Latest release observed
v0.4.5 points to beace3e52ceb491b8ef85b7e3f5439cb8273f248; its LICENSE is MIT.
The tag pyproject.toml declares version 0.4.4, reproduced by a second fetch at
that exact commit with identical bytes. PyPI metadata reports 0.4.5. Do not
silently equate tag, wheel and declared package version. Next compare the
published wheel/source hashes and import version before choosing a runtime.
Retained source/dependency/license metadata: ../progress/evidence/2026-10-13-162826/.

The upstream methods paper is Quantum 8, 1465 (2024),
https://doi.org/10.22331/q-2024-09-09-1465 . A citation is not electrical agreement.
The existing reference checker pins a separate HuggingFace dataset revision
0e25705f54c343fb96571ff15b6fd8375ca899aa (MIT dataset card) and WM1 design
revision 5329ff178980c16a299caa4804a2e5251e326833. It records no license file
for that pinned GDS repository; do not conflate code/dataset/design licenses
or vendor the GDS based on the SQuADDS code license.

## Dependencies and deduplication

Release metadata requires Python >=3.10, NumPy >=1.16.6,<2, pandas >=1.5,<3,
datasets >=4.8.1, scipy, scqubits, pyepr-quantum, scikit-rf and numerous
visualization/data packages. Required dependencies also include pyaedt==0.23,
quantum-metal>=0.5.0, PySide6>=6.10.1, Streamlit and Gmsh. These overlap entries
002, 003 and 005 but do not make those whole projects accepted or make SQuADDS
a duplicate target. NumPy <2 conflicts with the isolated SQcircuit runtime's
NumPy 2.5.3; use separate environments if package execution is needed. Do not
add this dependency stack to the lean base. An ANSYS client package is not
commercial solver access, which remains unavailable.

## Existing integration and evidence

`src/textlayout/external/squadds_mcp.py` is a frozen SquaddsPrior dataclass that
serializes PRIOR_ONLY and physics_verified=false. It has unannotated-unit float
maps and no live MCP connection or schema discovery. Reuse or tighten this
boundary; do not describe it as a working host integration.

`src/textlayout/verification/squadds_reference.py` already fetches hash-pinned
WM1 dataset/GDS assets and round-trips all four top variants. Retained repeated
results in docs/progress/evidence/2026-09-15-051619 report mask_geometry_passed,
four variants and six published measurement records. Device-to-top mapping is
null, electrical_reproduction_status is NOT_EVALUATED and error percent null.
This is mask import/export evidence, not a regenerated design or reproduced
measurement. Eight existing test_public_reference.py tests passed this audit;
no fresh geometry/solver execution or platform certification was performed.

At the pinned upstream source, squadds_mcp/server.py registers database,
analysis, interpolation, contribution and generation groups; startup constructs
SQuADDS_DB with network activity documented in source. Static wiring is not a
verified tools/list response. Host schemas, callable examples and installation
remain pending; contribution tools must not be invoked implicitly.

## Next bounded slice and acceptance

First reconcile release/wheel identity and select a hash-pinned, explicitly
licensed dataset slice. Prefer an offline typed prior importer with explicit
units, source revision, record identity and provenance; preserve PRIOR_ONLY.
Define deterministic selection/tie handling and malformed-data tests before
adding live retrieval. Reuse the existing WM1 geometry checker where relevant.
Acceptance requires actual repeated execution, independently checked dataset
selection/provenance, platform evidence and implementation commit. Electrical
validation additionally needs matched fabricated variant, stack/materials,
ports/junctions and converged extraction paired with measurements. Entry 007
remains unchecked until a bounded scope satisfies those criteria.
