# Local audit — 2026-09-13

Document class: MANUAL_DOCUMENTATION. This is a new local execution record,
not a replacement for the repository's generated historical status reports.

## Scope and provenance

The attached mission requests five sequential phases: environment and runtime
inspection, literature specification, quantitative comparison, open-source
augmentation, and reproducible delivery. The repository was cloned from
https://github.com/JungluChen/Text-to-Layout into this workspace, initially at
`f4da3b5e2d1a0093fde132e8dc46c52b508376ee`. The checkout was initially clean.
Host: macOS arm64. Isolated runtime: Homebrew Python 3.12.14 in `.venv`.
Dependency manager: uv 0.12.10; install uses the committed `uv.lock`.

## Phase 1 — discovery and environment

- Domain: microwave/superconducting chip layout, not document, room, or facility
  layout. The supported package is `src/textlayout`; `src/text_to_gds` and
  `src/textlayout/_legacy` are frozen compatibility implementations.
- Pipeline: deterministic prompt parser → Pydantic design intent/DSL → analytical
  sizing → polygon generators → verification/export → independent KLayout GDS
  readback → optional external solver adapters → typed evidence and reports.
  LangGraph sequences these stages. No API credentials or model weights are
  needed for the default pipeline.
- Existing integrations include gdsfactory, KLayout, NumPy, Matplotlib, Shapely
  (transitive), trimesh, optional scikit-rf, and adapters for FasterCap/FastCap,
  FastHenry, openEMS, JoSIM, and Palace. Existing fixtures and synthetic
  measurement records are not treated as fresh physical validation.
- Read `AGENTS.md` and `docs/development/reproduce_before_edit.md`. Failures must
  reproduce twice unchanged before tracked implementation is edited, then pass
  the original command twice and a regression check.

### Initial commands and observations

Commands ran from the parent workspace until the clone completed, then from
the repository root. Read-only discovery used `rg --files`, `cat`, and `sed`
over `AGENTS.md`, the diagnostic policy, `pyproject.toml`, `requirements.txt`,
`.gitignore`, `ARCHITECTURE.md`, `PROJECT_STATUS.md`, CI, supported source,
tests, solver installers, and existing reference metadata.

```sh
git clone https://github.com/JungluChen/Text-to-Layout.git
git status --short
git rev-parse HEAD
python3 --version
/Users/ludko/.local/share/comfy-mcp-venv/bin/uv --version
/Users/ludko/.local/bin/python3.11 --version
/Users/ludko/.local/share/comfy-mcp-venv/bin/uv sync --frozen \
  --python /opt/homebrew/bin/python3.12 --cache-dir .tools/uv-cache
.venv/bin/python .tools/audit_capture.py compile_baseline \
  .venv/bin/python -m compileall -q src scripts tests
```

- Initial clone and dependency-download attempts could not resolve remote hosts
  under restricted networking. Authorized network retries were used; this is
  an environment restriction, not a product defect. The clone retry succeeded.
- System `python3` is 3.9.6, below the package's >=3.11 requirement. An existing
  Python 3.12.14 installation was selected; no system Python was changed.
- A process-inspection attempt was denied by the sandbox; no source change was
  based on it. File size/progress logs sufficed.
- Installation stdout/stderr: `.tools/install.log`.
- Syntax compilation succeeded. Complete subsequent executable-command logs,
  exit codes, elapsed times, host/Python/dependency identity, selected environment
  variables, git SHA, and log hashes are captured in `out/audit/commands/` by
  the local recorder `.tools/audit_capture.py`. These are ignored local artifacts.
- Added numeric-conditioning regression cases before implementation changes.
  Their initial result and subsequent fixes are recorded below when executed.

## Phase 1 — executed results and reproduced parser fix

- `textlayout doctor --json` and the 0.6 pF IDC CLI smoke test succeeded.
  GDS/SVG/PNG/JSON outputs were nonempty; independent KLayout readback passed.
  The IDC and subsequent spiral previews were visually inspected.
- Cold imports took about 149 seconds while macOS font discovery populated
  Matplotlib's cache. Warm runs took about a second. A workspace-local
  `MPLCONFIGDIR` was used; no dependency code was changed for the cold cache.
- Numeric parsing converted `.6 pF` into `6 pF`, `6e-1 pF` into `1 pF`, and
  negative dimensions into positive values. The same regression command failed
  twice (11 failures, one pass). Signed/scientific numeric tokens and finite,
  positive quantity checks fixed the cause. Both post-fix runs passed all 12
  cases; surrounding parser/workflow regression tests passed.
- Initial full suite: 1,889 passed, 11 skipped, two failures. Both failures
  reproduced unchanged: sandbox denial of a local socket and process
  inspection. The same tests passed with those host permissions enabled.
  Neither test nor product behavior was weakened.

## Phase 2 — literature and protocol

`BENCHMARK_SPEC.md` fixes the population and metrics before the sizing changes.
Primary sources were checked for SQuADDS (Quantum 2024), PalaceForCQED (IEEE
ACES-China 2025), SQDMetal (explicitly a preprint), and Mohan et al. (IEEE JSSC
1999). The Ye and Mohan PDF tables were rendered and inspected directly.
Recent-paper frequency seeds are labeled as seeds, not matching devices.

The Mohan fixture contains **all 29 integer-turn square spirals** in Table IV.
Two transcription errors were corrected against the rendered original before
accepting the fixture: row 18 is 8.00 nH, not the adjacent ASITIC error of 8.8;
row 36's Wheeler error is 3.9%, not the adjacent model's 4.3%. No rows were
discarded because of poor model agreement, and no tolerance was relaxed.

## Phase 3 — repeated benchmark and diagnosis

The first draft harness required 0.1% while leaving the product's default
tolerance at 5%. Two unchanged runs exposed the mismatch. The harness was
corrected to request 0.1%; IDC then passed without a product change. This is a
protocol correction, not an IDC algorithm improvement.

The corrected baseline was run twice unchanged: **33/64 accepted**.

| Family | Baseline accepted | Cause |
| --- | ---: | --- |
| IDC | 16/16 | Correct once the requested tolerance matched the protocol |
| CPW | 1/16 | Gap override erased the solved impedance; worst error 81.313% |
| Spiral | 0/16 | Independent GDS width check failed at shortened reversed segments |
| Quarter-wave resonator | 16/16 | Analytical electrical-length consistency only |

## Phase 4 — open-source integration and verified fixes

- **CPW:** SciPy Brent root finding determines the elliptic-integral aspect
  ratio. Width and gap scale together to honor both user and process minima.
  Initial export runs exposed gdsfactory's even-DBU port-width requirement;
  repeated failures were fixed by rounding widths upward to a 2 nm grid.
  SciPy is now explicit in core dependencies. `uv lock` preserved every package
  version; its other changes normalize resolution markers. Frozen offline sync
  succeeded after the update.
- **Spiral geometry:** the path helper expanded endpoints before sorting;
  reversed segments therefore shrank. Sorting before expanding fixes the
  conductor joins. Regression tests check direction invariance, a single
  connected KLayout metal region, and actual drawn trace width.
- **Final verdict:** independent readback failures previously appeared in
  `klayout_readback.json` while `FromTextResult.ok` still reflected an earlier,
  weaker check. They now reach the returned report and CLI/API verdict.
- **Native solver:** built pinned FastHenry source
  `363e43ed57ad3b9affa11cba5a86624fad0edaa9` with clang. Two unchanged original
  build failures identified legacy C return/prototype diagnostics. Compatible
  C89 flags, `-fcommon` and specific diagnostic flags built a real arm64 Mach-O
  executable. No solver source was vendored into the product. The new native
  installer retains build commands, logs, compiler identity, revision and
  executable SHA-256; it was exercised with `--rebuild`.
- **Executable paths:** two identical relative-path solver runs failed after
  switching to the input directory. Absolute paths worked. Two additional
  discovery tests reproduced relative-path loss and inappropriate WSL routing
  of Unix ELF files. Explicit paths now resolve absolutely; ELF-to-WSL routing
  applies only on Windows. Both original commands and regressions passed twice.
- **Conductivity:** final unit review found `.units um` combined with
  `sigma=5.8e4`. Upstream `readGeom.c` divides sigma by the length-unit scale,
  so this represented 5.8e10 S/m. Two unchanged real-solver tests returned
  0.0256034 ohm instead of the 25.603448 ohm expected by Ohm's law for the normal
  metal assumption. The schema now exposes `conductivity_s_per_m` (default
  5.8e7); geometry retains it and the deck converts it to `sigma=58`. Both unit
  and real-solver tests passed twice, followed by 31 surrounding regression
  tests and repeated full benchmarks. Historical showcase files were not
  rewritten; their old conductivity assumptions must not be reused for R/Q.
- **AI review:** `demo.py` provides a one-command path and a machine-readable
  review containing requirements, equations, assumptions, evidence status and
  applicable engineering rules. Existing measurement calibration is documented
  as the path to process learning; no model training or measured device data
  was fabricated.

## Phase 5 — delivery and scientific limits

The final unchanged repeated benchmark gives **64/64** local geometry/target
passes. CPW worst analytical error is **0.0104%**. Fresh FastHenry runs pass
**16/16** local spiral targets within 5% (worst 4.802%); the 3 nH example
extracts **2.958308 nH**. Solver input, matrix, logs, identity and example GDS
are retained under `benchmarks/audit/fasthenry_3nh/`.

The published model reproduces **29/29** supported Mohan rows within the fixed
0.5 percentage-point rounding tolerance; maximum difference is 0.2146 pp.
The printed model has 8.9787% RMS measurement error on this identical subset;
this implementation has 8.9369%, with worst measurement APE 19.749%. This is
model reproduction, not a new measurement result or a field-solver validation
of the paper devices. Recent SQuADDS/PalaceForCQED/SQDMetal EM parity remains
`NOT_EVALUATED`. `--require-paper-parity` fails explicitly.

Validation includes the full test suite, strict product typing, lint, the README
claim gate, frozen environment sync, demo execution, the missing-simulation
failure gate, GDS inspection, a real-solver Ohm's-law check, and repeated numeric
benchmarks. The first post-fix full run passed 1,927 tests with 11 skipped; the
conductivity follow-up added two tests; the fresh full run passed **1,929 tests**,
with **11 skipped** in 80 seconds.
The many NumPy/Pydantic deprecation warnings in the existing chip-lattice tests
remain visible in the logs; they were not suppressed to manufacture a pass.

### Reproduction commands

```bash
uv sync --frozen --python 3.12
uv run python scripts/install_fasthenry_native.py
uv run python demo.py --prompt "Create a 3 nH spiral inductor with 4 turns, 4 um trace width and 2 um spacing" --out out/spiral --require-simulation
uv run python run_benchmark_validation.py --with-fasthenry
uv run pytest -q
uv run ruff check .
uv run mypy src/textlayout
uv run python scripts/validate_readme_claims.py
```

`scripts/capture_audit.py NAME COMMAND...` records complete command output and
identity under `out/audit/commands/`. Compact executed-command records,
versioned benchmark results and repeatability summaries are retained in
`benchmarks/audit/`. Numeric results and source-tree hashes match across the
final reruns; timestamps, output-directory paths and raw GDS timestamp hashes
are expected to differ. No commercial solver, API key, GPU or pretrained model
was used. Native Linux execution, full-wave paper parity, kinetic inductance,
mesh convergence and fabrication qualification remain outside the evidence
produced by this local Mac audit.
