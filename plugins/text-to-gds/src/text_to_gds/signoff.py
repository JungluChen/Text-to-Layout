"""Strict signoff level evaluation for Text-to-GDS artifacts.

The signoff evaluator is intentionally conservative.  It does not run solvers;
it only audits already-produced evidence and refuses upgraded labels when files
or provenance are missing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

REQUIRED_VALUE_FIELDS = {"value", "unit", "source", "method", "confidence", "file_path"}
INVALID_PHYSICAL_SOURCES = {"llm", "ai", "chatgpt", "prompt"}
EXECUTED_STATUSES = {"executed", "success", "ok", "passed"}
SKIPPED_STATUSES = {"skipped", "skip"}


def _exists(path: Any) -> bool:
    return bool(path) and Path(str(path)).is_file()


def _status(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("status") or payload.get("adapter_status") or "").strip().lower()


def validate_value_record(record: dict[str, Any]) -> dict[str, Any]:
    """Validate a physical numeric value record.

    Required schema:
    ``value, unit, source, method, confidence, file_path``.
    ``source="LLM"`` is always invalid for a physical value.
    """
    issues: list[str] = []
    missing = sorted(REQUIRED_VALUE_FIELDS - set(record))
    if missing:
        issues.append(f"missing value fields: {', '.join(missing)}")
    if str(record.get("source", "")).strip().lower() in INVALID_PHYSICAL_SOURCES:
        issues.append('source="LLM" is invalid for physical values')
    if "value" in record and not isinstance(record["value"], (int, float)):
        issues.append("value must be numeric")
    confidence = record.get("confidence")
    if confidence is not None:
        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            issues.append("confidence must be numeric")
        else:
            if not 0.0 <= confidence_value <= 1.0:
                issues.append("confidence must be between 0 and 1")
    if record.get("file_path") and not _exists(record["file_path"]):
        issues.append(f"file_path does not exist: {record['file_path']}")
    return {
        "schema": "text-to-gds.value-record-validation.v1",
        "passed": not issues,
        "issues": issues,
    }


def validate_value_records(records: list[dict[str, Any]] | None) -> dict[str, Any]:
    checks = [validate_value_record(record) for record in records or []]
    failed = [index for index, check in enumerate(checks) if not check["passed"]]
    return {
        "schema": "text-to-gds.value-record-set-validation.v1",
        "passed": not failed,
        "failed": failed,
        "checks": checks,
    }


def _solver_executed_with_output(solver: dict[str, Any]) -> bool:
    if _status(solver) not in EXECUTED_STATUSES:
        return False
    output = (
        solver.get("output_file")
        or solver.get("output_path")
        or solver.get("touchstone_path")
        or solver.get("result_path")
    )
    return _exists(output)


def evaluate_signoff(evidence: dict[str, Any]) -> dict[str, Any]:
    """Evaluate signoff Level 0-6 from explicit artifacts.

    Level meanings:
    0 geometry generated; 1 DRC passed; 2 extraction complete; 3 analytical
    sanity passed; 4 one real solver executed; 5 two independent solvers agree;
    6 measurement data imported and fitted.

    Topology confidence is checked at Level 4+: an unknown topology with
    confidence < 0.3 blocks progression to physics signoff.
    """
    blockers: list[str] = []
    value_validation = validate_value_records(evidence.get("values"))
    if not value_validation["passed"]:
        blockers.append("physical value provenance failed")

    level = -1
    if _exists(evidence.get("gds_path")):
        level = 0

    sidecar_path = evidence.get("sidecar_path")
    if level >= 0 and not _exists(sidecar_path):
        blockers.append("GDS has no sidecar; extraction cannot pass")

    drc = evidence.get("drc") or {}
    if level >= 0 and _status(drc) in {"passed", "ok"}:
        level = 1

    extraction = evidence.get("extraction") or {}
    extraction_file = extraction.get("result_path") or evidence.get("extraction_path")
    if level >= 1 and _exists(sidecar_path) and _exists(extraction_file):
        level = 2

    analytical = evidence.get("analytical_sanity") or {}
    if level >= 2 and analytical.get("passed") is True and value_validation["passed"]:
        level = 3

    solvers = evidence.get("solvers") or []
    skipped_solvers = [solver for solver in solvers if _status(solver) in SKIPPED_STATUSES]
    executed_solvers = [solver for solver in solvers if _solver_executed_with_output(solver)]
    if skipped_solvers and evidence.get("count_skipped_solver_as_evidence"):
        blockers.append("skipped solver cannot count as evidence")
    for solver in solvers:
        if _status(solver) in EXECUTED_STATUSES and not _solver_executed_with_output(solver):
            blockers.append(f"solver claimed executed without output file: {solver.get('solver', 'unknown')}")

    topology = evidence.get("topology") or {}
    topology_confidence = float(topology.get("confidence", 0.0) or 0.0)
    topology_device = str(topology.get("detected_device", "unknown") or "unknown")

    if level >= 3 and executed_solvers:
        level = 4

    if level >= 4 and topology_device == "unknown" and topology_confidence < 0.3:
        blockers.append(
            f"topology classification is unknown (confidence={topology_confidence:.2f}); "
            "requires higher-confidence topology for Level 5+"
        )

    agreement = evidence.get("solver_agreement") or {}
    if level >= 4 and len(executed_solvers) >= 2 and agreement.get("passed") is True:
        level = 5

    measurement = evidence.get("measurement") or {}
    measurement_file = measurement.get("file_path") or measurement.get("measurement_path")
    if level >= 5 and _status(measurement) in EXECUTED_STATUSES and _exists(measurement_file):
        level = 6

    label = "blocked"
    if level >= 6:
        label = "measurement-calibrated"
    elif level >= 5:
        label = "physics signoff"
    elif level >= 0:
        label = "iteration evidence"

    if level < 5 and evidence.get("claim") == "physics signoff":
        blockers.append("only Level 5+ can be called physics signoff")
    if level < 6 and evidence.get("claim") == "measurement-calibrated":
        blockers.append("only Level 6 can be called measurement-calibrated")

    result: dict[str, Any] = {
        "schema": "text-to-gds.signoff-level.v1",
        "level": max(level, 0),
        "label": label,
        "passed": not blockers,
        "blockers": blockers,
        "executed_solvers": [solver.get("solver", "unknown") for solver in executed_solvers],
        "skipped_solvers": [solver.get("solver", "unknown") for solver in skipped_solvers],
        "value_validation": value_validation,
    }
    if topology:
        result["topology"] = {
            "detected_device": topology_device,
            "confidence": topology_confidence,
        }
    return result

