# Integration source audit

**Document class: MANUAL_DOCUMENTATION.** Started 2026-09-26. This is a
source-and-scope audit of selected Priority 0 candidates, not installation,
platform, adapter or numerical validation. The 100-slot catalog intentionally
preserves user-supplied hints; corrections live here until a typed verified
source registry is specified.

| Slot | Source finding | Consequence |
| --- | --- | --- |
| 1 KQCircuits | [IQM's repository](https://github.com/iqm-finland/KQCircuits) describes a KLayout-based superconducting layout library and states GPL-3.0-or-later. | Canonical source and license identified. Import, geometry output, platform and solver behavior still need local checks. |
| 2 Qiskit Metal | The [maintainer repository](https://github.com/qiskit-community/qiskit-metal) now calls the project Quantum Metal, gives Apache-2.0, and says the current PyPI package is `quantum-metal`; the older `qiskit-metal` package is archived at a pre-v0.5 release. Its Ansys path requires AEDT and a license. | Audit the existing `layout` and newly declared `all` optional groups before migrating package names. Test imports and all platform locks in isolation; do not infer HFSS access from this package. |
| 6 SQcircuit | The [project site](https://www.sqcircuit.org/) links to [stanfordLINQS/SQcircuit](https://github.com/stanfordLINQS/SQcircuit), which identifies BSD-3-Clause. The supplied `squadds/SQcircuit` hint is therefore not the canonical source shown by the maintainers. | Retain the original hint for provenance, but use the verified repository when evaluating versions, equations and examples. No local installation or calculation is certified. |
| 8 QEDA | [qeda/qeda](https://github.com/qeda/qeda) is a MIT-licensed Node.js tool for schematic symbols and PCB land patterns. The supplied URL resolves, but its documented function does not match the Quantum Chip EDA pillar's intended superconducting layout/physics role. | Reclassify or reject this slot during catalog deduplication; do not install it as a quantum solver or count it toward quantum-chip capability. |

These four source reviews establish only the linked repositories' stated
identity, purpose and license at review time. They do not justify changing
`doctor.integration_targets[*].source_verified` globally or asserting that
the other 96 supplied names resolve. Review the remaining sources, aliases,
licenses and maintenance states in bounded groups before adding adapters.
