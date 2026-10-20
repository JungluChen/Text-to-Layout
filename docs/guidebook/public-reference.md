# Check the pinned public reference

**Document class: MANUAL_DOCUMENTATION.** A packaged CLI workflow; reference
geometry equivalence is distinct from electrical prediction or calibration.

```sh
textlayout verify --reference --out out/reference
# Repeat without network, using the verified user cache:
textlayout verify --reference --offline --out out/reference-repeat
```

By default the cache is `~/.cache/textlayout/squadds`; `--cache PATH` overrides
it. The command downloads only the two pinned data assets, checks their
SHA-256 before caching, executes KLayout on all four GDS top variants, and
writes `results.json` plus per-variant geometry comparisons. No upstream code
is downloaded or executed. Exit 0 means mask round-trip equivalence passed;
exit 2 means a failed comparison or unavailable/corrupt source. Missing offline
assets require an initial online run. Preserve a corrupt cache for diagnosis
before replacing it from the pinned source. The GDS source's distribution
license is unresolved; it is fetched as a local reference, never bundled.

The comparison uses exact KLayout region XOR and label equality at identical
database units: zero XOR is justified for a lossless mask round trip, not as
an electrical tolerance. WM1's six published electrical records are displayed
with their source; they are not predictions by this project. Device-to-mask
mapping and independently determined circuit inputs are missing, so electrical
reproduction stays `NOT_EVALUATED`. Do not infer capacitance from measured
anharmonicity and then claim that fitted spectrum independently validates it.

`REFERENCE_AGREED` is a new evidence-contract state above `PHYSICS_VERIFIED`
and below `MEASUREMENT_CORRELATED`. It inherits the existing solver/target
requirements (and convergence in canonical evidence). Additional
`PublicReferenceComparison` provenance requires a pinned HTTPS source,
revision, retained source hash, source selection, published value/units,
library/version, hashed execution output and a retained JSON tolerance
declaration containing `tolerance_percent` and `justification`. A mismatch
cannot construct this state. It remains an executed comparison result with
its error retained. No numerical tolerance or `REFERENCE_AGREED` claim is
invented for the WM1 electrical case.

Canonical records carry this block in `extraction_config.public_reference`;
the compatibility QuantityEvidence projection retains it. The confidence
ordering adds REFERENCE=5 and moves MEASURED to 6; persisted status names keep
their meaning. Reference agreement does not replace measurement calibration
or fabrication signoff. Consumers should use enum names rather than assuming
integer confidence values.

Pinned reference JSON is decoded as UTF-8 explicitly on every platform,
including Windows with a legacy default locale. A decoding failure produces
a failed mask check; it never becomes a successful electrical comparison.

## Read one offline frequency prior

From the repository with the pinned dataset cached by the reference command:

```python
from pathlib import Path
from textlayout.external.squadds_mcp import load_wm1_prior

prior = load_wm1_prior(
    Path.home() / ".cache/textlayout/squadds/measured_device_database.json",
    "qubit_1",
)
print(prior.to_dict())
```

Expected: resonator_frequency_hz=6116000000, qubit_frequency_hz=4216000000,
anharmonicity_hz=-153000000, PRIOR_ONLY and physics_verified=false. The
frequency unit is Hz, not rad/s. Original fields (including the upstream
Anharmocity_MHz spelling), units and scale factors remain in dataset_metadata.
Local repeated API execution checked all six records against independently
transcribed Hz values. No package installation or numerical simulation occurs.

This API needs only the database file; it neither fetches nor requires the GDS.
On missing data, obtain the pinned asset using the earlier reference workflow
or its documented source URL. On a hash mismatch preserve the file for diagnosis
and restore the exact pinned revision; do not edit the expected hash. Select
qubit_1 through qubit_6 explicitly; nearest-neighbour search is not provided.
No geometry, capacitance, junction value or uncertainty is inferred. Estimated
and extracted fields outside these three frequency fields are not imported.

AI prompt: “Read the pinned WM1 qubit_1 prior with load_wm1_prior; show original
units, source revision and converted Hz. Keep PRIOR_ONLY and explain the missing
device-to-layout mapping before using the values as design inputs.”

MCP integration and GUI screenshots for this loader remain pending.

### Offline CLI

From the repository, after caching the pinned database:

```sh
uv run textlayout squadds-prior ~/.cache/textlayout/squadds/measured_device_database.json --device qubit_1
```

The expected values and provenance are identical to the Python example above.
The command prints the prior JSON to stdout and does not write files. Exit 0
means the prior was read; it does not mean physics validation. Missing files
or changed hashes produce JSON on stderr and exit 1. A missing or invalid
--device produces argparse usage and exit 2. All six qubit IDs are explicit;
there is no default or closest-match selection. Repeat the command against
the same bytes for identical output. Never redirect stdout onto the source
database; use a different file if saving the result.

### Dedicated prior-data platform benchmark

The manual `squadds-prior-integration` workflow uses Python 3.12 and the frozen
core environment on Windows, macOS and Linux. It downloads only the pinned
dataset, executes all six CLI selections twice, and checks expected Hz, source
identity, PRIOR_ONLY and identical repeats. It retains source bytes, command
records, stdout/stderr, runtime identity and hashes. No upstream SQuADDS package
or solver runs. Workflow existence is not platform acceptance: download and
independently inspect all packets after a successful exact-SHA run. On failure,
preserve the artifact and rerun unchanged before editing; never promote a
partial packet or omit a failed platform.

### Optional SQuADDS runtime audit

The offline `squadds-prior` CLI does not require the upstream SQuADDS package.
Do not add its full dependency stack to the base environment merely to read
pinned priors. An audited macOS import failure occurs with SQuADDS 0.4.5,
NumPy 1.26.4 and PyArrow 26.0.0 despite a passing metadata check. A separately
resolved PyArrow-21-constrained environment imported successfully twice; see
[the runtime audit](../integrations/squadds.md). This is an experimental
macOS import result, not a supported full SQuADDS installation or solver result.
Keep the standalone environment and failed logs for diagnosis; use the existing
offline prior CLI for its documented scope. Windows/Linux runtime and database
initialization remain pending. No GUI screenshot applies to this import probe.

### Offline SQuADDS metadata worker

Developer interface: run `src/textlayout/external/_squadds_metadata_worker.py
DATABASE NEW_OUTPUT.json` with the explicitly selected isolated Python runtime.
Requires SQuADDS 0.4.5, datasets 5.0.1, PyArrow 21.0.0, NumPy 1.26.4 and
pandas 2.3.3 (complete audited runtime pins retained in the integration audit).
It checks dataset SHA256/1 MiB bound and installed helper hash, uses normal
upstream imports with offline dataset flags, and writes a new raw JSON packet.
Existing outputs are refused. No base dependency is added, no SQuADDS_DB
constructor or remote retrieval is invoked. Optional imports may create library
caches; use the isolated runtime/cache configuration documented in the audit.

Output is PRIOR_ONLY, physics_verified=false, assessment_status=NOT_EVALUATED.
Configuration names are identifiers, not simulation values. The observed
SQUILL/N/A foundry discrepancy is preserved. This raw worker is not a typed
public runner, CLI command, MCP endpoint or electrical validation; product-side
assessment, timeout/log retention and Windows/Linux execution remain pending.
No UI or screenshot delivered. On errors retain stderr, repair the explicit
runtime/input and retry with a new output path; do not promote partial results.

### SQuADDS metadata packet assessment

`textlayout.external.squadds_metadata_assessment.assess_metadata(database: bytes,
packet: dict)` checks raw worker records, lookup results, pinned hashes/revision,
versions and status flags against an independent projection of the pinned local
dataset. No defaults, filesystem writes, optional imports or processes. Returns
frozen MetadataAssessment(records_checked, dataset_sha256, PRIOR_ONLY, false);
malformed or mismatched data raises ValueError. Runtime strings are required
but are self-reported: data agreement does not prove execution identity.
The upstream foundry discrepancy is preserved. Boolean/numeric substitutions
and extra fields are rejected. No electrical or measurement promotion.

Example: read the pinned database bytes and raw JSON packet, call assess_metadata,
and expect records_checked=3 for the retained example. On rejection retain both
inputs and inspect source/identity differences; do not rewrite the evidence to
make it pass. AI prompt: “Assess this raw metadata packet against pinned local
source bytes, report discrepancies, and keep process verification separate.”
Product runner, timeout/log retention and Windows/Linux execution remain next.
No public CLI/MCP tool or GUI/screenshot is added by this pure assessment API.
