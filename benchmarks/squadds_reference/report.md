# SQuADDS WM1 reference verification

**Executed:** 2026-09-14, native Apple Silicon, gdsfactory and KLayout.
This population uses the original published mask. It does not use generated
frequency prompts as substitutes for paper devices.

| Original top variant | Extent | Layers checked | XOR area on every layer | Labels/bounding box | Result |
| --- | --- | ---: | ---: | --- | --- |
| TOP | 5 mm × 5 mm | 4 | 0 um² | Identical | PASS |
| TOP$1 | 5 mm × 5 mm | 4 | 0 um² | Identical | PASS |
| TOP$2 | 5 mm × 5 mm | 4 | 0 um² | Identical | PASS |
| TOP$3 | 5 mm × 5 mm | 4 | 0 um² | Identical | PASS |

Each variant was imported and exported with gdsfactory, then compared
independently with KLayout at the original 0.001 um database unit. The union
of layers in both files is checked, so an added or missing layer cannot be
hidden by a matching bounding box. Two unchanged executions produced identical
geometry comparisons and measurement records. Original large-record warnings
remain in the local command logs.

The six published WM1 records contain these values:

| Device | Resonator GHz | Qubit GHz | Anharmonicity MHz | Extracted coupling MHz |
| --- | ---: | ---: | ---: | ---: |
| qubit_1 | 6.116 | 4.216 | -153 | 61 |
| qubit_2 | 6.353 | 3.896 | -154 | 67 |
| qubit_3 | 6.472 | 4.451 | -189 | 67 |
| qubit_4 | 6.568 | 3.586 | -164 | 66 |
| qubit_5 | 6.655 | 4.101 | -210 | 48 |
| qubit_6 | 6.704 | 3.881 | -176 | 39 |

These are source-reported values, not new measurements or this project's
predictions. Attribution: [SQuADDS database, pinned revision](https://huggingface.co/datasets/SQuADDS/SQuADDS_DB/tree/0e25705f54c343fb96571ff15b6fd8375ca899aa),
[original WM1 design](https://github.com/LFL-Lab/design_schema_WM1/tree/5329ff178980c16a299caa4804a2e5251e326833),
and [Shanto et al., Quantum 8, 1465](https://doi.org/10.22331/q-2024-09-09-1465).
Full original numeric fields and file hashes are in [results.json](results.json).

**Electrical reproduction: NOT_EVALUATED.** The top variant corresponding to
the measured chip is not established. A complete physical stack, port and
junction setup, and converged extraction are still needed. The database labels
the fabrication recipe confidential. No electrical error is assigned and no
generic-process calibration is performed from these records.

```bash
uv run python scripts/validate_squadds_reference.py --out out/squadds_reference/run_1
uv run python scripts/validate_squadds_reference.py --out out/squadds_reference/run_2 --offline
```

The script downloads only two hash-pinned assets, totaling less than 1 MiB.
It never executes the upstream notebook. GDS inputs/exports stay in ignored
local storage; this folder retains the comparison metadata and numeric facts.
The measured database declares MIT licensing; the pinned design repository
does not include a license file.
