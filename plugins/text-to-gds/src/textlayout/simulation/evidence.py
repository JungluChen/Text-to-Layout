"""Strict circuit-simulation evidence labels and the full evidence record.

The label vocabulary is fixed and ordered. Rules (enforced here and in tests):

- ``*_INPUT_PREPARED``    — files were generated; nothing was executed.
- ``SKIPPED_*_ABSENT``    — the simulator is not installed; inputs may exist.
- ``*_EXECUTED``          — a real subprocess/module execution happened.
- ``*_TRANSIENT_PARSED``  — the execution produced a parseable waveform.
- ``*_RESONANCE_CHECKED`` — a resonance was extracted and compared with the
  analytical ``f0 = 1/(2π√(LC))`` expectation.
- ``*_GAIN_CHECKED``      — pump/signal transient data existed and FFT-based
  gain extraction ran. Never claimable from prepared inputs.
- ``FAILED``              — execution or parsing failed; reason is mandatory.
- ``PHYSICS_VERIFIED`` is reserved for the complete benchmark (geometry
  extraction *and* circuit checks within tolerance) and is owned by
  :mod:`textlayout.evidence`, not by any single simulator.
"""

from __future__ import annotations

from typing import Any

from textlayout.simulation.models import SimulationResult

# General (backend-agnostic) labels.
INPUT_PREPARED = "INPUT_PREPARED"
SIMULATOR_ABSENT = "SIMULATOR_ABSENT"
SIMULATOR_EXECUTED = "SIMULATOR_EXECUTED"
TRANSIENT_PARSED = "TRANSIENT_PARSED"
RESONANCE_CHECKED = "RESONANCE_CHECKED"
GAIN_CHECKED = "GAIN_CHECKED"
FAILED = "FAILED"

GENERAL_LABELS = (
    INPUT_PREPARED,
    SIMULATOR_ABSENT,
    SIMULATOR_EXECUTED,
    TRANSIENT_PARSED,
    RESONANCE_CHECKED,
    GAIN_CHECKED,
    FAILED,
)

#: Simulators with a reserved backend-specific label family.
CIRCUIT_SIMULATORS = ("JOSIM", "PSCAN2", "WRSPICE")

#: How far up the evidence ladder each stage sits. ``FAILED`` is reachable
#: from anywhere; everything else may only move forward (monotone honesty).
_STAGE_RANK = {
    SIMULATOR_ABSENT: 0,
    INPUT_PREPARED: 0,
    SIMULATOR_EXECUTED: 1,
    TRANSIENT_PARSED: 2,
    RESONANCE_CHECKED: 3,
    GAIN_CHECKED: 3,
}

CIRCUIT_EVIDENCE_SCHEMA = "textlayout.circuit-simulation-evidence.v1"


def backend_label(simulator: str, stage: str) -> str:
    """Backend-specific label, e.g. ``("JoSIM", "INPUT_PREPARED") → JOSIM_INPUT_PREPARED``."""
    key = simulator.upper().replace("-", "").replace(".", "")
    if key not in CIRCUIT_SIMULATORS:
        raise ValueError(f"unknown circuit simulator {simulator!r}")
    if stage == SIMULATOR_ABSENT:
        return "SKIPPED_SOLVER_ABSENT"
    if stage == FAILED:
        return FAILED
    if stage not in _STAGE_RANK:
        raise ValueError(f"unknown evidence stage {stage!r}")
    # The general stage is SIMULATOR_EXECUTED; backend labels shorten it to
    # e.g. JOSIM_EXECUTED per the fixed vocabulary.
    suffix = "EXECUTED" if stage == SIMULATOR_EXECUTED else stage
    return f"{key}_{suffix}"


def general_stage(label: str) -> str:
    """Map any backend-specific or general label back to its general stage."""
    if label == "SKIPPED_SOLVER_ABSENT":
        return SIMULATOR_ABSENT
    if label in GENERAL_LABELS:
        return label
    for key in CIRCUIT_SIMULATORS:
        if label == f"SKIPPED_{key}_ABSENT":
            return SIMULATOR_ABSENT
        prefix = f"{key}_"
        if label.startswith(prefix):
            stage = label[len(prefix) :]
            # JoSIM keeps two historical labels beyond the shared vocabulary.
            if stage in ("JJ_DYNAMICS_CHECKED", "PARAMETRIC_GAIN_CHECKED"):
                return GAIN_CHECKED if stage == "PARAMETRIC_GAIN_CHECKED" else TRANSIENT_PARSED
            if stage == "EXECUTED":
                return SIMULATOR_EXECUTED
            if stage in _STAGE_RANK:
                return stage
    raise ValueError(f"unknown evidence label {label!r}")


def validate_transition(old_label: str | None, new_label: str) -> None:
    """Reject evidence-ladder demotions; ``FAILED`` is always reachable.

    A record may move forward (prepared → executed → parsed → checked) or
    fail, but a later stage can never be silently downgraded back to an
    earlier claim — that would rewrite history.
    """
    new_stage = general_stage(new_label)
    if old_label is None or new_stage == FAILED:
        return
    old_stage = general_stage(old_label)
    if old_stage == FAILED:
        raise ValueError("a FAILED record is terminal; start a new attempt instead")
    if _STAGE_RANK[new_stage] < _STAGE_RANK[old_stage]:
        raise ValueError(
            f"illegal evidence demotion {old_label} → {new_label}; "
            "evidence may only advance or fail"
        )


def circuit_evidence(
    result: SimulationResult,
    *,
    simulator: str,
    executable: str | None,
    version: str | None,
) -> dict[str, Any]:
    """The complete, self-describing evidence record for one simulator attempt.

    Every field the honesty contract demands is present even when empty, so a
    reader can distinguish "not applicable" from "not recorded".
    """
    artifacts = dict(result.artifacts)
    waveform_columns = result.extracted_quantities.get("signal_names")
    return {
        "schema": CIRCUIT_EVIDENCE_SCHEMA,
        "simulator": simulator,
        "executable": executable,
        "version": version if version is not None else result.solver_version,
        "input_file": artifacts.get("input"),
        "output_file": artifacts.get("result") or artifacts.get("expected_output"),
        "command": list(result.command),
        "working_directory": str(result.output_dir) if result.output_dir is not None else None,
        "stdout_file": artifacts.get("solver_stdout"),
        "stderr_file": artifacts.get("solver_stderr"),
        "return_code": result.return_code,
        "runtime_seconds": result.runtime_seconds,
        "waveform_columns": list(waveform_columns) if isinstance(waveform_columns, list) else [],
        "extracted_metrics": {
            k: v for k, v in result.extracted_quantities.items() if k != "signal_names"
        },
        "target_comparison": result.target_comparison,
        "status": result.status,
        "status_label": result.evidence_level,
        "failure_reason": result.reason if result.status == "failed" else None,
        "warnings": list(result.warnings),
        "artifacts": artifacts,
    }
