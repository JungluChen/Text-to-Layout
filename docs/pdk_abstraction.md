# Foundry PDK abstraction

**Why this exists:** `generic_2metal` (the built-in default technology) is a
minimal layer/rule stack — just enough for the geometry engine to draw
polygons and check minimum width/spacing. It has no metal thickness, no sheet
or kinetic inductance, no dielectric loss tangents, no density rules, and no
named JJ process parameters. Every other cQED design-loop upgrade in this
project (EPR/coherence, JJ yield, chip collisions) needs those richer numbers.
This module is the typed, versioned schema for them — the `textlayout.pdk`
package.

## Relationship to `Technology`

`textlayout.pdk.PDK` is the rich schema; `textlayout.models.Technology` is
the minimal one the geometry engine, verification checks, and exporters
already depend on. Rather than rewrite that pipeline, a `PDK` is *projected*
down to a `Technology` with the same name:

```python
from textlayout.pdk import load_pdk, pdk_to_technology

pdk = load_pdk("src/textlayout/knowledge/pdks/example_superconducting_pdk.yaml")
technology = pdk_to_technology(pdk)   # a real Technology, usable anywhere
```

`default_technology_library()` does this automatically at startup: every
`*.yaml` file under `src/textlayout/knowledge/pdks/` is loaded and registered
under its own PDK name. `generic_2metal` itself stays the hardcoded
`Technology` object (zero behavior change for existing examples); a
malformed PDK file is skipped, never fatal, at startup.

## What a PDK carries

| Section | Fields |
| --- | --- |
| `grid` | Manufacturing grid, default min width/spacing fallbacks. |
| `substrate` | Material, εr, loss tangent, thickness. |
| `layers[]` | Purpose (`metal`\|`junction`\|`ground`\|`via`\|`text`\|`marker`\|`dielectric`), GDS layer/datatype, min width/spacing, thickness, sheet resistance, **kinetic inductance** (pH/sq — superconducting films), loss tangent, density-rule placeholder (min/max fill fraction). |
| `junction_process` | Target Jc, wafer-level Jc sigma, min junction area, Tc — feeds `textlayout.yield_model` directly. |

Every `PDK` carries `foundry_validated: bool`, `source: str`, and
`calibration_status: str` — a more granular three-way status than the bool
alone: `illustrative` | `internal_calibrated` | `foundry_calibrated`.
`internal_calibrated` means the process has been correlated against real
measurements (see `textlayout.measurement`) but is not foundry-qualified.
The two are kept mutually consistent by validation:
`foundry_validated=True` if and only if `calibration_status="foundry_calibrated"`.
**No PDK shipped in this repository sets either** — both examples are
illustrative, enforced by a test
(`test_no_shipped_pdk_claims_foundry_calibrated`).

## The two shipped examples

| PDK name | What it's for |
| --- | --- |
| `generic_2metal_pdk` | The built-in `generic_2metal` numbers, re-expressed in the PDK schema — format compatibility and testing, not a new process. |
| `example_superconducting_pdk` | A richer illustrative example: 3-metal stack, kinetic inductance, junction dielectric loss tangent, density rules, JJ process parameters. Order-of-magnitude figures for a generic Nb/Al-on-Si process, **not measured on any specific process**. |

Both are usable today with zero new commands:

```bash
textlayout generate examples/benchmarks/01_idc_0p6pf/layout.json --out out/idc          # generic_2metal (unchanged)
# ... or edit layout.json's "technology" field to "example_superconducting_pdk"
```

```bash
textlayout pdk list                              # every registered technology name
textlayout pdk info example_superconducting_pdk  # full PDK provenance + process parameters
```

## Evidence provenance

Every `textlayout generate`/`verify`/`prompt` JSON payload carries a
`pdk_provenance` field: `{available, pdk_name, pdk_version, file_path,
file_hash_sha256, calibration_status, foundry_validated, source}` when the
spec's technology is backed by a PDK YAML, or `{available: false, note: ...}`
when it isn't (e.g. the hardcoded `generic_2metal` Technology, which predates
the PDK schema). The file hash is a SHA-256 of the exact YAML bytes — computed
at report time, not stored on the `PDK` model itself, so it reflects the exact
file on disk even if its content changes without a version bump.

```python
from textlayout.pdk import describe_pdk_file, find_pdk_provenance_for_technology

provenance = find_pdk_provenance_for_technology("example_superconducting_pdk")
print(provenance.file_hash_sha256, provenance.calibration_status)
```

## DRC and LVS hooks

- **Min width / min spacing / layer existence**: already enforced against the
  projected `Technology` by the existing `textlayout.verification.checks`
  pipeline — no duplicate logic.
- **Density** (`textlayout.pdk.drc.check_density`): a placeholder. It
  evaluates one fill-fraction number against a layer's configured
  `min_density_fraction`/`max_density_fraction` — the caller must compute
  that fraction (drawn area / window area) since tiling a layout into
  density-check windows is future work, not implemented here.
- **LVS** (`textlayout.pdk.lvs`): a typed `Netlist`/`LVSChecker` interface
  with one honest implementation, `NotImplementedLVSChecker`, which reports
  `SKIPPED_NOT_IMPLEMENTED` — never a fabricated `MATCH`. Real device
  recognition and connectivity extraction from geometry is a substantial
  undertaking on its own and is not attempted here.

## What this is not

**Real fabrication requires a foundry-qualified PDK** — measured process
statistics (Jc distribution, loss tangents, sheet resistance), a
foundry-validated design-rule deck, and real density/antenna/LVS checks none
of which exist in this repository. `example_superconducting_pdk` exists to
wire the EPR, yield, and chip-collision loops together end to end with
plausible numbers — not to approve a mask for tape-out.
