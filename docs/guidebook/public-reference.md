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
