# Benchmark Artifact & Determinism Policy

This document defines which benchmark artifacts are committed to the repository,
which are reproducible, how provenance is tracked, and how to avoid unnecessary
git churn when regenerating them.

The guiding rule: **running `scripts/generate_benchmarks.py` twice in a row must
produce no git diff.** This is enforced empirically (see "Verifying determinism"
below) and is the reason for every choice on this page.

## Committed artifacts

Each `examples/benchmarks/<name>/` folder commits a complete, self-describing
packet:

| File | Kind | Source of truth? | Reproducible bytes? |
| --- | --- | --- | --- |
| `prompt.md` | input | yes (hand-written) | n/a |
| `layout.json` | input | **yes** — the DSL the rest is derived from | n/a |
| `output.gds` | binary artifact | no (derived) | yes (normalized) |
| `output.svg` | text artifact | no (derived) | yes |
| `output.png` | binary artifact | no (derived) | yes, per matplotlib version |
| `output.json` | text artifact | no (derived) | yes |
| `verification.json` | text artifact | no (derived) | yes |
| `analytical_estimate.md` | text artifact | no (derived) | yes |
| `simulation_plan.md` | text artifact | no (derived) | yes |
| `evidence.md` | text artifact | no (derived) | yes |
| `report.md` | text artifact | no (derived) | yes |
| `simulation/` | solver input files | no (derived) | yes |

`layout.json` is the only source of truth. Every other file is regenerated from
it; if it changes, all derived artifacts are regenerated.

## Provenance

`output.json` and `verification.json` each carry a `provenance` block:

```json
{
  "layout_json_sha256": "53c96cae…",
  "generator_version": "0.2.0",
  "generated_at": "normalized",
  "timestamp_normalized": true,
  "source_layout_path": "benchmarks/01_idc_0p6pf/layout.json"
}
```

* `layout_json_sha256` — SHA-256 of the source `layout.json`. If the committed
  artifacts were generated from a different DSL than the one on disk,
  `scripts/check_benchmarks.py` reports them as **STALE**.
* `generator_version` — the `textlayout` version that produced the packet.
* `generated_at` — `"normalized"` in the default (reproducible) mode. The real
  wall-clock time is **not** committed; it is written to a git-ignored
  `.generation_meta.json` sidecar instead.
* `timestamp_normalized` — `true` when `generated_at` was normalized.

`scripts/check_benchmarks.py` additionally enforces that the provenance block in
`output.json` and `verification.json` are **identical**, so the two halves of a
packet can never drift apart silently.

## How determinism is achieved

Three sources of non-determinism were identified and removed:

1. **`generated_at` timestamp** (JSON churn). Normalized to the sentinel
   `"normalized"`; the real time goes to the git-ignored sidecar.
2. **GDS top-cell UUID suffix** (GDS churn). gdsfactory assigns every export a
   unique `<name>_<uuid8>` top cell to avoid process-global registry
   collisions. After export, `textlayout.exporters.gds_exporter.canonicalize_gds`
   reads the file back through KLayout, renames the single top cell to a stable
   name, and rewrites it.
3. **GDSII BGNLIB/BGNSTR wall-clock timestamp** (GDS churn, 1 s resolution).
   KLayout writes the current time into these records by default; the rewrite
   sets `SaveLayoutOptions.gds2_write_timestamps = False`, zeroing them.

PNG previews pin their metadata (`Software` chunk) so the only remaining
variation is the matplotlib rasteriser version — see the caveat below.

## Avoiding unnecessary git diffs

`scripts/generate_benchmarks.py` is **skip-if-unchanged by default**:

* Before regenerating a `ready` benchmark, it compares the live
  `layout.json` SHA-256 against the committed provenance hash. If they match and
  all required artifacts exist, the benchmark is skipped — its committed bytes
  are never touched.
* This means a second run is a no-op, regardless of binary determinism.

Flags:

| Flag | Effect |
| --- | --- |
| *(none)* | Reproducible mode + skip-if-unchanged (recommended; used in CI). |
| `--force` | Regenerate even when artifacts are current (still reproducible). |
| `--allow-timestamps` | Embed wall-clock `generated_at` (non-reproducible; debugging only). |
| `--strict` | Treat incomplete `todo` benchmarks as failures. |

## Verifying determinism

```bash
# 1. A forced regeneration is byte-identical across separate processes:
python scripts/generate_benchmarks.py --force
md5sum examples/benchmarks/*/output.gds examples/benchmarks/*/output.png > /tmp/a
python scripts/generate_benchmarks.py --force
md5sum examples/benchmarks/*/output.gds examples/benchmarks/*/output.png > /tmp/b
diff /tmp/a /tmp/b   # -> no output

# 2. The default run is a no-op when nothing changed:
python scripts/generate_benchmarks.py
git diff --quiet examples/benchmarks/ && echo "clean"
```

## Known limitations

* **PNG bytes depend on the matplotlib version.** The geometry and metadata are
  fixed, but a matplotlib upgrade can change anti-aliasing/font rasterisation and
  therefore the PNG bytes. PNGs are previews only — never an EM-solver input —
  so this is cosmetic. When it happens it is a one-time, reviewable diff.
* **GDS bytes depend on the KLayout/gdsfactory versions.** The same caveat
  applies: an upgrade can re-order records. The geometry (layers, polygons,
  ports) is unchanged and is what downstream tools read.
* Determinism is enforced only for `ready` benchmarks. `geometry_candidate`
  (e.g. SQUID) and `infeasible` (e.g. 5 MHz LC) benchmarks are not regenerated
  by the script and therefore never churn.

In short: **the JSON/SVG/GDS/PNG artifacts are reproducible for a pinned toolchain,
and a re-run never rewrites unchanged artifacts.** Where full binary stability is
not guaranteed across tool upgrades, the affected files (PNG, GDS) are derived
previews/exports whose semantic content is verified by `check_benchmarks.py`.
