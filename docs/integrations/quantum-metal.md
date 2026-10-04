# Quantum Metal / Qiskit Metal — entry 002 in progress

Document class: MANUAL_DOCUMENTATION.

The maintained upstream package is `quantum-metal`; this repository still locks
older `qiskit-metal` 0.1.2. No core dependency migration is made here. Exploratory
execution uses a separate Python 3.12 environment with quantum-metal 0.9.0.
Upstream tag v0.9.0 is revision
[15587c1284a95354d427540864de4206daa2f064](https://github.com/qiskit-community/qiskit-metal/tree/15587c1284a95354d427540864de4206daa2f064),
with Apache-2.0 licensing. Installation and in-memory QComponent checks do not
complete integration acceptance.

## Explicit mask fixture and independent gate

The real upstream `TransmonPocket` fixture has two 455 × 90 um charge pads,
a 30 um gap, a 650 × 650 um pocket, zero rotation/translation and no connectors.
The chip is explicitly 2 × 2 mm. GDS generation uses the upstream gdstk renderer;
readback below uses KLayout independently. Ground plane is enabled, cheese and
no-cheese display layers are disabled, and no junction GDS is supplied.

**This is a partial mask fixture, not a fabricated transmon or validated qubit.**
The junction table contains a design element but no fabrication junction is
exported. The upstream log warns that the junction file is absent. Do not supply
a fake junction, or report electrical connectivity, capacitance or frequency.

Run the gate from the repository root against an exported fixture:

```sh
uv run --no-sync python scripts/check_quantum_metal_transmon_gds.py /path/to/transmon.gds --out /path/to/new-readback.json
```

1. Keep the original exporter request/options, dependency versions, logs and GDS.
2. Require one top cell and a 1 nm database grid. Layer 1/datatype 10 contains
   the two pads; layer 1/datatype 0 contains the ground plane minus the pocket.
   This is the observed explicit upstream fixture mapping, not a foundry PDK.
3. Read all top-cell descendant shapes. Require exactly those two nonempty
   layers and zero integer-grid XOR against independent rectangle references.
   Pad area is 81900 um²; ground-plane area is 3577500 um². The different GDS
   user unit (1 mm) must not be mistaken for micrometres; KLayout converts shape
   coordinates to its reported database grid.
4. Exit 0 establishes only this fixed mask check. `junction_verified` stays
   false and `electrical_validation` stays `NOT_EVALUATED`. Changed dimensions
   require a separately specified reference, not relaxed thresholds.
5. Exit 1 means geometry was rejected; retain the JSON failure reason. Existing
   report paths are refused. Missing/corrupt input raises an error and cannot
   produce a verified report. Retry into a new report path after diagnosis.

The gate is a benchmark script, not a new product CLI/API or MCP endpoint.
Its synthetic regression fixtures test rejection behavior; actual upstream
execution evidence is retained separately in the dated progress report.

## Reproduced export limitation

With `ground_plane=False`, upstream `export_to_gds` returned its success code 1
but wrote an empty GDS library in two unchanged executions. Source inspection
shows shape conversion is conditional on `ground_plane=True`; the disabled
path has no replacement conversion. The gate rejects both empty artifacts.
Enabling the ground plane changes the requested mask semantics: the explicit
2 mm fixture above is a separate experiment, not a claim to fix upstream's
pad-only export. No upstream library was patched.

## Remaining acceptance

Entry 002 stays unchecked pending platform acceptance. The typed adapter and
public command described below now implement the bounded positive-mask scope,
validate inputs and retain provenance/failures. Repeat real export/readback on
macOS, Windows and Linux before acceptance. Broader transmon delivery requires an explicit real junction source
and connectivity/fabrication validation; electrical validation requires real
solver execution and appropriate references. GUI screenshots remain pending a
real installed application; this headless gate supplies no GUI evidence.

AI prompt: “Inspect the Quantum Metal exporter log and independently check this
explicit mask fixture. Separate exporter return code, nonempty geometry, mask
comparison, fabrication-junction completeness and electrical validation. Keep
entry 002 pending until its typed adapter and platform evidence exist.”

## Typed product operation (platform verification pending)

`TransmonMaskRequest` and `generate_transmon_mask` in
`textlayout.external.quantum_metal_mask` expose the bounded positive-mask operation.
Required numeric micrometre fields are `pad_width_um`, `pad_height_um`,
`pad_gap_um` (up to 10000), `pocket_width_um`, `pocket_height_um` (up to 50000),
and `chip_width_um`, `chip_height_um` (up to 100000). All must be positive,
finite and multiples of 0.002 um so centred boundaries lie on the 1 nm grid.
Strings, booleans and unknown fields are rejected. The pocket must strictly
contain both pads and their gap; the chip must strictly contain the pocket.
No connector, rotation, junction or layer customization is supported.

Prepare an external environment without changing the core:

```sh
uv venv .qm-env --python 3.12
uv pip install --python .qm-env quantum-metal==0.9.0 gdstk==1.0.1
uv run --no-sync textlayout quantum-metal-mask examples/integrations/quantum-metal-mask.json --python .qm-env/bin/python --out out/qm-first
uv run --no-sync textlayout quantum-metal-mask examples/integrations/quantum-metal-mask-small.json --python .qm-env/bin/python --out out/qm-small
```

On Windows, pass `.qm-env/Scripts/python.exe`. Explicit external interpreter
selection preserves the lean base install. The worker is packaged in the wheel;
no upstream modules are imported in the core. KLayout readback occurs in the
core after checking exporter versions, request identity and GDS SHA-256.

Inspect `manifest.json` for `execution_completed`, `return_code`,
`geometry_verified`, `junction_verified`, and independent readback. The first
three are separate results; junction verification is always false for this
operation. Readback keeps electrical validation NOT_EVALUATED. Exact zero XOR
is required against the supplied dimensions. Changed dimensions are checked
against newly constructed independent integer-grid references, not the fixed
fixture's rectangles. The historical benchmark script still checks only its
original fixed fixture through the same implementation.

The command exits zero only after independent mask verification; missing runtime,
nonzero process exit, timeout, malformed report, mismatched input/hash or failed
readback cannot pass. Logs survive failures/timeouts. Existing output directories
are refused. Keep failed packets and retry into a fresh directory after correcting
the runtime/request. No checkpoint/resume is offered. No MCP method is added.

The `quantum-metal-integration` manual workflow runs both example inputs twice
on each platform and retains all packets. Acceptance remains pending until these
actual outputs are reviewed. A complete fabricated transmon remains outside this
mask operation because a real junction and its process specification are absent.
