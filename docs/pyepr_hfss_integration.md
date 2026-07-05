# Wiring a real pyEPR / HFSS session into `textlayout.epr`

**Status: not implemented here, and intentionally not stubbed with speculative
code.** `PyEPRBackend.analyze()` (`src/textlayout/epr/backends.py`) reports
`EPR_SKIPPED_SOLVER_ABSENT` honestly when pyEPR is not importable, and raises
`NotImplementedError` when it is — because driving a live HFSS eigenmode
session requires an interactive Ansys session (typically Windows + a
pywin32/COM connection) that cannot exist in this development environment or
in CI. Writing integration code against an API we cannot run — and whose
exact shape has changed across pyEPR versions — risks shipping something that
*looks* wired up but silently doesn't work, which is worse than the current
honest stub. This document is the contract a real implementation must meet,
for whoever has the actual HFSS + pyEPR access to build and test it.

## The fast path: you probably don't need to write any textlayout code

If you can get participation numbers out of pyEPR at all (via whatever
version and workflow you're already using), the quickest way to use them here
is **not** through `PyEPRBackend` — it's through the backend that already
exists and is tested: [`FieldEnergyImportBackend`](epr_coherence.md#field-energy-import-ci-safe-real-data-shaped).

1. Run your own pyEPR/HFSS session however you normally do.
2. Export each region/material's electric field energy integral to a JSON
   file matching this schema (see the real, committed example at
   `examples/epr_fixtures/field_energy_export_example.json`):

   ```json
   {
     "schema": "textlayout.field-energy-export.v1",
     "source": "<describe your real pyEPR/HFSS session here, not 'synthetic'>",
     "component": "<component name>",
     "frequency_ghz": <eigenmode frequency>,
     "regions": [
       {"region": "substrate", "electric_energy_j": <real number>},
       {"region": "metal_substrate", "electric_energy_j": <real number>},
       ...
     ]
   }
   ```

3. Point `FieldEnergyImportBackend(path_to_your_export)` at it. You get a
   real `FIELD_ENERGY_IMPORTED` result — genuinely solver-derived evidence —
   with zero new textlayout code required. Region names must match keys in
   whatever `MaterialsDB` you pass (default: `illustrative_silicon_db()`);
   supply your own materials YAML (`load_materials_db`) if your process's
   loss tangents are measured, not illustrative.

This is almost certainly less work than writing and debugging a live-session
COM adapter, and it decouples "I have participation numbers" from "textlayout
knows how to drive Ansys," which is a much smaller, more testable surface.

## The full path: driving a live HFSS session from `PyEPRBackend`

If you want `textlayout epr` to launch and drive HFSS itself (status
`EPR_EXECUTED`, not `FIELD_ENERGY_IMPORTED`), here is the contract
`PyEPRBackend.analyze()` must satisfy — verify every API call below against
**your installed pyEPR version's own documentation**; the class/method names
here reflect the historically stable pyEPR workflow but pyEPR has had breaking
API changes across major versions:

1. **Never claim `EPR_EXECUTED` unless pyEPR's own analysis call returned
   successfully and produced real per-region participation numbers.** Any
   exception, timeout, or empty result must fall through to a `FAILED`-style
   result or a clear error — never a fabricated participation record.
2. **Build one `ParticipationRecord` per region/material** with:
   - `p_electric` (and `p_magnetic` if your pyEPR version exposes magnetic
     participation) computed from pyEPR's own energy participation ratios —
     do not rescale or reinterpret them.
   - `tan_delta` from the caller-supplied `materials: MaterialsDB` (matched by
     region name), exactly as `AnalyticalEPRBackend`/`FieldEnergyImportBackend`
     already do — never invent a materials database inline in this backend.
   - `confidence` reflecting pyEPR's own convergence/error metrics if
     available; otherwise a value near 1.0, higher than
     `FieldEnergyImportBackend`'s `0.6` (a live, this-project-executed
     extraction is stronger evidence than an imported file of unknown
     provenance).
   - `source` naming the live session precisely, e.g.
     `f"pyEPR {pyEPR.__version__} live HFSS session: {design_name}"`.
3. **Populate `EPRResult.provenance`** with at least: pyEPR version, HFSS
   version (if queryable), the HFSS project/design name, and the eigenmode
   solve setup name — enough that a report reader can find the exact session
   that produced these numbers.
4. **`assumptions` must state real limitations of the run**, not the generic
   analytical-backend disclaimers — e.g. mesh refinement level, whether
   convergence was reached, which modes were included.
5. **Add a real integration test** using pyEPR's own mocking/test utilities if
   it has them, or a recorded-session fixture — not a plain
   `unittest.mock.MagicMock` standing in for the entire pyEPR surface, which
   would prove the glue code runs without proving it's calling pyEPR
   correctly.

## Why this is written as a contract, not code

Every other backend in this project (`AnalyticalEPRBackend`,
`FieldEnergyImportBackend`, every solver adapter in
`textlayout.simulation`) was built against something we could actually run
and test in this environment — even the "skipped" paths are exercised by
real code taking a real absent-tool branch. `PyEPRBackend`'s live-session path
is the one piece of this project where that isn't true, and the honest
response to "we can't test it" is "don't ship untested code that claims to
work," not "ship plausible-looking code anyway."
