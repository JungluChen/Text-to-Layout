# FasterCap Integration Audit

Date: 2026-07-03

## Scope

Reviewed:

- `simulation/idc_fastercap/generate_fastercap_input.py`
- `simulation/idc_fastercap/run_fastercap.py`
- `src/textlayout/simulation/fastercap.py`
- `src/textlayout/simulation/models.py`
- `SOLVER_EVIDENCE_CONTRACT.md`
- `README.md`

## Findings and disposition

| Area | Finding | Disposition |
| --- | --- | --- |
| Discovery | Explicit path, `TEXTLAYOUT_FASTERCAP`, `.tools/FasterCap/bin`, and `PATH` use the shared priority order. A Linux ELF found from native Windows cannot run directly. | Kept the shared discovery order and reject ELF binaries on native Windows. Run repository-built FasterCap from WSL/Linux. |
| CLI target | The wrapper did not read `spec.target.capacitance_pf` and exposed no tolerance option. Executed results were therefore not target-compared. | Fixed. `--tolerance-pct` defaults to 5%, and the DSL target is passed to `run_fastercap`. |
| Terminal result artifact | `simulation_result.json` was written only after successful parsing. Skipped, launch-failed, non-zero, and parser-failed states had no terminal evidence record. | Fixed. Every terminal path writes `textlayout.simulation-result.v1`. |
| Process logs | Normal subprocess completion retained stdout/stderr, but launch errors/timeouts did not. Empty channels also produced empty files. | Fixed. Every attempted command has non-empty stdout/stderr capture artifacts; a silent channel contains an explicit no-output marker. Missing-solver skips do not claim an attempted command. |
| Non-zero exit | Non-zero status was honest, but return code and runtime were omitted from the returned result. | Fixed. Status remains `failed`, with command, return code, runtime, and logs retained. |
| Parser failure | Parser failure was honest but lacked a persisted terminal result and structured parsed/compared flags. | Fixed. Status is `failed`; `capacitance_matrix_parsed=false`, `target_compared=false`, and logs/result are retained. |
| Unit conversion | Labeled matrices convert farads by `1e12`, femtofarads by `1e-3`, picofarads by `1`, and nanofarads by `1e3`. Native FasterCap `Capacitance matrix is:` output is interpreted as farads and multiplied by `1e12`. | Correct. Tests exercise the pF form; parser rejects unknown units and malformed matrices. |
| Mutual capacitance | The adapter uses `abs(C[0][1])`, appropriate for the negative off-diagonal Maxwell-matrix coupling term. | Correct for the two-conductor IDC model. |
| Physics gate | `SimulationResult.physics_verified` already required execution, parsed quantities, and an in-tolerance comparison. The aggregate IDC workflow incorrectly added a circuit-resonance requirement intended for JPA. | Fixed. IDC verification uses the capacitance evidence gate; JPA still requires its additional circuit check. |
| Report | Reports distinguished broad evidence statuses but did not consistently show executed/parsed target-comparison facts. | Fixed. Reports state solver execution, extracted and target capacitance, signed error, tolerance, verification, and failure/skip reason. |
| README | Most claims were conditional, but the open-source status table still described IDC as input-preparation-only. | Fixed. README now states conditional execution/verification and the committed-artifact rule. |
| Claim validation | A non-empty `simulation_result.json` alone could satisfy an execution claim, and physics validation used a separate aggregate evidence shape. | Fixed. Claims require an executed result plus non-empty stdout/stderr; `PHYSICS_VERIFIED` additionally requires a parsed matrix and `within_tolerance=true`. |

## Evidence gate

`PHYSICS_VERIFIED` is reachable only when all of these conditions hold:

1. A discovered FasterCap/FastCap command completed with return code 0.
2. Captured stdout and stderr artifacts exist and are non-empty.
3. Solver stdout was accepted by the capacitance-matrix parser.
4. A matrix with at least two rows and columns was extracted in pF.
5. The absolute off-diagonal mutual capacitance was compared with the DSL target.
6. The absolute percentage error is within the configured tolerance.

Prepared input, an analytical capacitance estimate, executable discovery, or a
successful process with malformed output cannot satisfy this gate.

## Model limitation

The generated IDC deck is a zero-thickness, effective-medium electrostatic
correlation model. A passing target comparison does not make the layout
fabrication-ready and does not replace mesh convergence, explicit dielectric
interface modeling, process-qualified DRC, or an independent solver cross-check.
