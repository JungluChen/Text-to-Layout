# Palace next-generation validation report

## Release lineage

- Starting commit: `d133eaccd27e2fd47986f7c6c3fc11bdd219acde`
- Operational Palace release: `2d084489`
- Final validated implementation commit: `747dbc317340c6feaf75471ee6b55578bc8fd056`
- Branch: `main`
- Palace: 0.17.0, executable SHA-256
  `ad43ec030f51435f32150a5c72cb324ca03083d2ffc2f91405bbf41c6bc2240f`
- Gmsh: 4.15.2
- MPI: Open MPI 4.1.6

The operational v021 run remains `CONVERGENCE_FAILED`. Its historical
scientific verdict was not rewritten.

## Implemented work

The release adds an amplitude-, global-phase-, ordering-, and direction-invariant
quarter-wave field evaluator; KLayout/Gmsh/Palace geometry and boundary audit;
an explainable multimode classifier; a bounded real Palace diagnostic catalog;
global Hungarian mode assignment; and physically localized Gmsh controls for
CPW gaps, coupling gap, open and grounded ends, conductor interfaces, and the
substrate-vacuum interface.

Global assignment uses frequency cost, electric and magnetic reference MAC,
regional-signature distance, resonator-localization distance, and physical-class
mismatch. Ambiguity is determined by forbidding each selected edge and solving
the global assignment again.

## Quarter-wave evaluator

Twelve manufactured tests pass. They cover the ideal profile, coordinate
reversal, swapped endpoint metadata, complex global phase, amplitude scaling,
shuffled samples, noise, endpoint singularity exclusion, half-wave and uniform
rejection, longitudinal phase variation, and coupler-localized contamination.

The retained v021 fields show that its formerly selected mode 2 is not the
quarter-wave target: combined profile correlation is `-0.992726814`, electric
open/ground ratio is `0.181160129`, and magnetic ground/open ratio is
`0.233246778`.

## Geometry and boundary audit

The audit passes with no geometry blocker. The physical grounded endpoint is
`(0, 0)` um, the open endpoint is `(0, 4918.4652)` um, and the coupling gap is
4 um. KLayout connectivity checks pass. All 12 Gmsh physical groups match the
typed FEM model. Palace resolves PEC attributes `[10, 11, 12, 30, 31]`; the
substrate-vacuum interface attributes `[20, 21]` are not shorted as PEC.

Critical regions are still represented by compatibility volume attributes,
not complete metal-air and metal-substrate surface partitions. This blocks
predictive interface EPR.

## Diagnostic multimode solve

Palace executed one rank with eight retained modes and returned code 0 in
357.581779 seconds. Input and solver outputs are hashed. Frequency was not the
primary selection rule.

| Mode | Frequency (GHz) | Class | Confidence |
|---:|---:|---|---:|
| 1 | 5.007997027 | QUARTER_WAVE_RESONATOR | 0.860165 |
| 2 | 5.684244414 | SUBSTRATE_MODE | 0.926255 |
| 3 | 9.954098955 | HALF_WAVE_RESONATOR | 0.926079 |
| 4 | 13.748018282 | UNKNOWN | 0.601014 |
| 5 | 17.026804241 | SUBSTRATE_MODE | 0.928358 |
| 6 | 20.116648454 | UNKNOWN | 0.538087 |
| 7 | 22.979797637 | UNKNOWN | 0.549795 |
| 8 | 28.207876964 | SUBSTRATE_MODE | 0.932749 |

Mode 1 is the only accepted quarter-wave target. This proves that the previous
nearest-to-6-GHz selection had tracked the wrong physical mode. It does not
prove convergence.

## Targeted A/B refinement

The targeted scale-3 Gmsh smoke mesh has 261,841 tetrahedra, minimum quality
0.0935621, and mean quality 0.721368.

An initial Palace A/B attempt with `UpdateFraction=0.70` grew 263,313 elements
to 861,370 and was terminated by the configured 7 GiB process-group RSS limit.
Observed peak was 8,076,271,616 bytes; no owned process remained.

The bounded replacement used `UpdateFraction=0.20` and solved both states:

| State | Elements | DOF | Frequencies (GHz) |
|---|---:|---:|---|
| A | 263,313 | 333,954 | 5.485387034, 5.928063192, 10.963587122 |
| B | 381,853 | 474,616 | 5.600931038, 6.063004839, 11.182125279 |

Palace returned code 0. Peak process-group RSS was 7,276,322,816 bytes, below
the 7,516,192,768-byte limit. The untracked index-wise frequency shifts are
2.1064%, 2.2763%, and 1.9933%.

State A returned `TARGET_MODE_NOT_FOUND`. Mode 1 has quarter-wave profile
correlation 0.989686 and resonator localization 0.743518, but fails all four
endpoint node/antinode gates: electric open/ground ratio 2.59435, magnetic
ground/open ratio 2.71418, electric node residual 0.385453, and magnetic node
residual 0.368436. Therefore the index-wise shifts are diagnostic only. No
target MAC, mesh-convergence, or promotion claim is allowed.

## Evidence status

- Operational execution: `SIMULATION_EXECUTED`
- Historical v021 scientific status: `CONVERGENCE_FAILED`
- Targeted A/B scientific status: `SIMULATION_INVALID`
- Physics verification: not reached
- Independent-reference promotion: not reached

## Blocked downstream work

The following work was deliberately not executed because the physical target
was absent at the first targeted state:

- Three-state convergence: blocked by `TARGET_MODE_NOT_FOUND`.
- Domain and boundary sensitivity: blocked by missing mesh convergence.
- Polynomial-order comparison: blocked by missing mesh convergence.
- EPR and interface participation: blocked by missing convergence and incomplete
  explicit critical-surface partitioning.
- Q and T1 uncertainty: blocked by missing converged participation.
- EM-to-circuit export: blocked by missing converged target mode.
- scqubits and JosephsonCircuits validation: blocked by missing reduced model.
- Minimal Josephson and JPA benchmarks: blocked by missing validated linear model.
- Yield, sensitivity, optimization, and real optimized rerun: blocked by missing
  predictive linear and nonlinear models.

No acceptance threshold was weakened to advance these phases.

## Final validation

- Pytest: 1,872 collected; 1,864 passed; 8 skipped; 0 failed; 159.50 seconds.
  The increase from the 1,842-test baseline is exactly 30 new tests.
- Ruff: pass.
- mypy: pass for 177 `textlayout` source files.
- compileall: pass.
- `uv build`: pass; sdist and wheel 0.3.0 produced.
- Clean wheel installation: 138 packages installed; import and CLI both report
  0.3.0.
- Palace capability: `SMOKE_TEST_PASSED`.
- External registry and NOTICE drift: pass, zero problems.
- README claims: pass.
- Benchmark audit: pass.
- Canonical evidence consistency: 6/6 showcases pass.
- Generated project status: current.
- SPDX release SBOM: fail. The retained Syft SPDX parses and contains KLayout
  0.30.9, but its OCI digest does not match the pinned release image digest.
  Docker is unavailable locally, so a correctly linked SBOM could not be
  regenerated. This is a release blocker, not Palace physics evidence.

## Evidence artifacts

- `out/audit/palace_operational_release.json`
- `out/audit/palace_quarter_wave_evaluator_validation.json`
- `out/audit/palace_model_audit/model_audit.json`
- `out/audit/palace_preliminary_mode_catalog_v021.json`
- `out/audit/palace_diagnostic_v022/mode_catalog.json`
- `out/audit/palace_targeted_ab_v024_summary.json`
- `out/audit/palace_targeted_ab_v024_report.md`
- `out/audit/final_pytest_junit.xml`
- `out/audit/final_evidence_consistency.json`
