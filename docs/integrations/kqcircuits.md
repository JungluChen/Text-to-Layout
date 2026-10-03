# KQCircuits acceptance work — checklist entry 001

Document class: MANUAL_DOCUMENTATION.

**Scoped product adapter implemented; platform command verification pending.**
The supported operation is straight CPW gap-mask geometry, not the full toolkit.
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

- DONE for this harness: [run 37108393257](https://github.com/JungluChen/Text-to-Layout/actions/runs/37108393257) at db7cdc10e5360a079ae01d0b75127d8e014c90d4 passed on Linux, Windows and macOS. Six report/GDS packets were downloaded, hashes verified and both cases passed each time. This covers the harness, not the product adapter.
- Typed adapter, CLI/API and guidebook command are implemented below. Local
  verification is retained in the dated product report; exact-SHA three-platform
  product-command verification remains required. No MCP endpoint is exposed.
- Retain source/license, execution, reference and platform records with the
  implementation commit in completed.json in a subsequent documentation commit.
- Keep electrical simulation/convergence separate from this geometry-only scope.

AI prompt: “Run the isolated KQCircuits geometry acceptance twice into fresh
directories. Report package versions, GDS units, gap-layer mapping, XOR area,
output hashes and platform. Do not claim impedance, convergence or a completed
integration from these geometry checks.”


## Product command and typed API

Prepare a separate Python 3.12 environment with the three pinned packages above.
Then run the shared core command with an explicit external interpreter:

```sh
uv run --no-sync textlayout kqcircuits-cpw examples/integrations/kqcircuits-cpw.json --python /path/to/external/python --out out/kqc-product
```

On Windows use the external environment's `Scripts/python.exe`; macOS/Linux
use `bin/python`. The core never imports KQCircuits. It executes its packaged
worker under the external interpreter and exchanges request/GDS/JSON/log files.
No packages are installed implicitly. The worker is included in the wheel under
textlayout.external, rather than depending on a checkout script. Installed-wheel
execution is recorded separately from checkout execution in the progress report.

`StraightCPWRequest` and `generate_straight_cpw` in
`textlayout.external.kqcircuits_bridge` form the typed Python API. Required
numeric fields: `length_um` (0 < value <= 100000), `width_um` and `gap_um`
(0 < value <= 10000). Unknown fields, strings, booleans, nonfinite/nonpositive
numbers and off-grid values are rejected. Length/gap use a 0.001 um grid;
width uses 0.002 um so its half-width boundaries also lie on the grid.
The fixed illustrative upstream face/layer mapping is retained; this is not a PDK.

The result separates `execution_completed`, `return_code` and
`geometry_verified`. Exit zero alone is insufficient: a matching one-case
report, requested dimensions and GDS hash must be present. A verified geometry
has no canonical physical-evidence promotion. Geometry checks use exact zero
mask XOR on the 1 nm grid; area comparison permits one square grid cell
(0.000001 um²) for floating-point area arithmetic, not an electrical tolerance.

Request and worker hashes, exact command and typed result are in manifest.json;
stdout/stderr are retained even on a timeout. A missing interpreter/runtime,
nonzero exit, missing report, wrong dimensions or GDS hash mismatch cannot be
reported as verified. Existing output directories are refused. Recovery: inspect
stderr.txt and failure_reason, fix the external environment, then use a fresh
output directory. Do not overwrite the failed packet or relabel it successful.

CLI returns 0 only for verified geometry and 1 for a failed/unavailable run or
invalid request. Typed API returns a failure result for process/report failures;
invalid request, timeout configuration or an existing output directory raises.
There is no new HTTP or MCP endpoint. AI prompt: “Use kqcircuits-cpw with the
explicit external interpreter and this micrometre request. Retain the manifest,
GDS and logs; report geometry verification separately from electrical simulation.”
