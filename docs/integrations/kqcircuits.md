# KQCircuits acceptance work — checklist entry 001

Document class: MANUAL_DOCUMENTATION.

**In progress; not yet a completed integration.** The first executable slice
is a process-isolated geometry acceptance harness, not a general product adapter.
No physics is implemented in this harness and no EM solver is invoked.

## Pinned source and scope

KQCircuits 4.9.11 corresponds to upstream tag v4.9.11, commit
[14483b00d20a4033971d08b99428b4ec9ace9d58](https://github.com/iqm-finland/KQCircuits/tree/14483b00d20a4033971d08b99428b4ec9ace9d58).
The source is GPL-3.0-or-later. Keep the existing external-process GDS/JSON
boundary; no upstream source is copied into the deterministic core. The repository
lock already selects 4.9.11; this work does not upgrade it or the base install.

The harness uses KLayout 0.30.12 and independent GDS reader gdstk 0.9.61.
Every report records installed dependency versions, platform, inputs, exported
GDS hashes, units and geometric error. Upstream platform claims are not local
acceptance. The manual kqcircuits-integration workflow exercises Linux, Windows
and macOS separately and retains two runs per platform.

## Execute and inspect

From the repository root with Python 3.12 and uv available:

```sh
uv run --isolated --no-project --python 3.12 --with kqcircuits==4.9.11 --with klayout==0.30.12 --with gdstk==0.9.61 python scripts/verify_kqcircuits_geometry.py --out out/kqc-first
uv run --isolated --no-project --python 3.12 --with kqcircuits==4.9.11 --with klayout==0.30.12 --with gdstk==0.9.61 python scripts/verify_kqcircuits_geometry.py --out out/kqc-repeat
```

Use fresh output directories; existing directories are refused to preserve
prior evidence. Missing optional packages or version mismatch is a failure,
not a simulated output. No commercial access or paid service is required.

1. The real upstream WaveguideCoplanarStraight generates two cases: length,
   width, gap = (1000,10,6) and (250,20,8), all in micrometres.
2. Read the exported GDS using gdstk, not the generating KLayout engine.
3. Verify 1 um GDS user units and 1 nm database precision. Resolve the gap layer
   by its upstream semantic name and retain its numeric layer/datatype.
4. Compare the gap-mask polygons to two independently specified rectangles.
   For these grid-aligned coordinates, the predeclared XOR area is exactly zero
   on the 1 nm grid; expected total gap area is 2 × length × gap. Two polygons
   are required. Exit 0 means these geometric checks pass, not impedance or
   resonator accuracy, fabrication readiness or complete KQCircuits support.
5. Keep report.json and the two GDS files together. Binary hashes may differ
   between exports due to timestamps; compare geometry metrics, not only bytes.

Local macOS execution and repeat passed both cases. An intentional negative
control increased each generated gap by 1 um and was rejected. It is clearly
labelled diagnostic evidence, not a failed accepted design. No GUI screenshot
is provided: this is a headless execution harness, not a delivered desktop app.

## Remaining acceptance before checking 001

- Review exact-SHA three-platform execution artifacts and compare repeats.
- Implement a typed product adapter with explicit supported shape/units,
  invalid-input and unavailable-runtime behavior, using existing geometry and
  evidence contracts; this harness alone does not supply that adapter.
- Add CLI/API and guidebook examples for the delivered adapter. Do not invent
  an MCP method until the real host schema exposes one.
- Retain source/license, execution, reference and platform records with the
  implementation commit in completed.json in a subsequent documentation commit.
- Keep electrical simulation/convergence separate from this geometry-only scope.

AI prompt: “Run the isolated KQCircuits geometry acceptance twice into fresh
directories. Report package versions, GDS units, gap-layer mapping, XOR area,
output hashes and platform. Do not claim impedance, convergence or a completed
integration from these geometry checks.”
