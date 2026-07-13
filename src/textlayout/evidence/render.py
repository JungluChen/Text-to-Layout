"""Project canonical evidence into every public artifact.

The dependency graph is explicit and one-directional:

    evidence/canonical.json                     (the only source of truth)
      -> simulation.json, simulation/simulation.json
      -> openems_result.json, extraction/capacitance_result.json  (solver level)
      -> workflow_trace.json
      -> report.md            [generated block: evidence-status]
      -> README.md            [generated block: evidence-status]
      -> examples/showcase/index.json
      -> README.md (top level) [generated blocks: showcase-table, evidence-summary]

Nothing downstream stores a status of its own; each is rewritten from the
record. A downstream artifact therefore cannot hold a higher confidence than
its upstream evidence, and correcting the record corrects every consumer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textlayout.evidence.canonical import CanonicalEvidence
from textlayout.evidence.consistency import (
    EVIDENCE_BLOCK,
    GENERATED_BEGIN,
    GENERATED_END,
    classify_outcome,
)
from textlayout.evidence.contract import EvidenceStatus

#: Solver-level status strings keep their `<QUANTITY>_EXTRACTED` vocabulary
#: while a number was genuinely extracted; otherwise they carry the evidence
#: status, because there is no extracted quantity to name.
_EXTRACTED_OK = frozenset({EvidenceStatus.SIMULATION_EXECUTED, EvidenceStatus.PHYSICS_VERIFIED})


def _dump(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _quantity_key(record: CanonicalEvidence) -> str:
    unit = (record.target_unit or "").lower()
    return f"{record.target_quantity}_{unit}" if unit else record.target_quantity


def _target_comparison(record: CanonicalEvidence) -> dict[str, Any]:
    return {
        "quantity": _quantity_key(record),
        "extracted": record.extracted_value,
        "target": record.target_value,
        "error_pct": record.error_percent,
        "tolerance_pct": record.tolerance_percent,
        "within_tolerance": record.target_tolerance_passed is True,
        "target_tolerance_passed": record.target_tolerance_passed is True,
    }


def render_simulation_json(record: CanonicalEvidence, path: Path) -> bool:
    payload = _load(path)
    if payload is None:
        return False
    payload["status"] = record.status.value
    payload["scientific_validation_level"] = record.scientific_validation_level
    payload["target_tolerance_passed"] = record.target_tolerance_passed
    payload["extracted_value"] = record.extracted_value
    payload["extracted_unit"] = record.extracted_unit
    payload["solver_executed"] = record.status not in {
        EvidenceStatus.ANALYTICAL_ONLY,
        EvidenceStatus.SKIPPED_SOLVER_ABSENT,
        EvidenceStatus.SIMULATION_INPUT_PREPARED,
    }
    payload["target_compared"] = record.error_percent is not None
    if "target_comparison" in payload or record.target_value is not None:
        payload["target_comparison"] = _target_comparison(record)

    # simulation.json also embeds per-quantity QuantityEvidence records. They are
    # a second representation of the same claim and must be projected too --
    # exactly the kind of hidden duplicate that let the resonator drift survive.
    evidence = payload.get("evidence")
    if isinstance(evidence, list):
        for item in evidence:
            if not isinstance(item, dict) or item.get("quantity") != record.target_quantity:
                continue
            item["status"] = record.status.value
            item["scientific_validation_level"] = record.scientific_validation_level
            item["target_tolerance_passed"] = record.target_tolerance_passed
            item["extracted_value"] = record.extracted_value
            item["extracted_unit"] = record.extracted_unit
            item["target_value"] = record.target_value
            item["target_unit"] = record.target_unit
            item["error_percent"] = record.error_percent
            item["tolerance_percent"] = record.tolerance_percent
            item["parser"] = record.parser
            item["canonical_evidence_id"] = record.evidence_id
            if record.invalidation_reason:
                item["notes"] = [f"SIMULATION_INVALID: {record.invalidation_reason}"]

    payload["canonical_evidence_id"] = record.evidence_id
    payload["scientific_validation_level"] = record.scientific_validation_level
    payload["target_tolerance_passed"] = record.target_tolerance_passed
    _dump(path, payload)
    return True


def render_solver_result_json(record: CanonicalEvidence, path: Path) -> bool:
    """Rewrite a solver-level result file so it agrees with canonical evidence."""
    payload = _load(path)
    if payload is None:
        return False
    previous = str(payload.get("status", ""))

    if record.status in _EXTRACTED_OK and record.extracted_value is not None:
        # keep the solver-level vocabulary when a number really was extracted
        status = previous if classify_outcome(previous) == "EXTRACTED" else previous
        payload["status"] = status
        quantities = payload.get("extracted_quantities")
        if isinstance(quantities, dict):
            quantities[_quantity_key(record)] = record.extracted_value
            payload["extracted_quantities"] = {
                key: value
                for key, value in quantities.items()
                if not (isinstance(value, float) and value != value)  # drop bare NaN
            }
        else:
            payload["extracted_quantities"] = {_quantity_key(record): record.extracted_value}
    else:
        payload["status"] = record.status.value
        payload["extracted_quantities"] = {}
        if record.invalidation_reason:
            payload["invalidation_reason"] = record.invalidation_reason

    if record.target_value is not None:
        payload["target_comparison"] = _target_comparison(record)
    if record.superseded is not None:
        payload["superseded_claim"] = record.superseded.model_dump(mode="json")
    payload["canonical_evidence_id"] = record.evidence_id
    _dump(path, payload)
    return True


def render_workflow_trace(record: CanonicalEvidence, path: Path) -> bool:
    """Stamp the canonical status onto a trace without rewriting its history.

    A workflow trace records what each node observed *at the time the workflow
    ran*. Those per-node summaries are audit history: editing them to match a
    later correction would falsify the record of the run. Instead the trace is
    stamped with the authoritative status, and the status the run itself
    reported is preserved under `run_reported_status`.

    Consumers must read `canonical_evidence_status`; the embedded per-node
    strings are historical and are never a claim about current evidence.
    """
    payload = _load(path)
    if payload is None:
        return False
    reported = _run_reported_status(payload)
    payload["canonical_evidence_id"] = record.evidence_id
    payload["canonical_evidence_status"] = record.status.value
    payload["scientific_validation_level"] = record.scientific_validation_level
    payload["target_tolerance_passed"] = record.target_tolerance_passed
    if reported and reported != record.status.value:
        payload["run_reported_status"] = reported
        payload["historical_note"] = (
            f"This trace records a run that reported {reported}. Canonical evidence "
            f"for this design is {record.status.value}. The per-node summaries below "
            "are preserved as the historical record of that run and are NOT a claim "
            "about current evidence."
        )
    else:
        payload.pop("run_reported_status", None)
        payload.pop("historical_note", None)
    _dump(path, payload)
    return True


def _run_reported_status(payload: dict[str, Any]) -> str | None:
    """The final evidence status the recorded run itself observed."""
    existing = payload.get("run_reported_status")
    if isinstance(existing, str):
        return existing
    seen: str | None = None
    for node in payload.get("nodes", []):
        if not isinstance(node, dict):
            continue
        for value in node.values():
            if not isinstance(value, str):
                continue
            for status in EvidenceStatus:
                if f"'evidence_status': '{status.value}'" in value:
                    seen = status.value
    return seen


def _block(name: str, body: str) -> str:
    return f"{GENERATED_BEGIN.format(name=name)}\n{body.rstrip()}\n{GENERATED_END.format(name=name)}"


def evidence_block_markdown(record: CanonicalEvidence) -> str:
    """The one authoritative status section for a showcase document."""
    lines = [
        "",
        "## Evidence status",
        "",
        "<!-- Generated from evidence/canonical.json. Do not edit by hand. -->",
        "",
        f"- **Scientific validation level:** `{record.scientific_validation_level or record.status.value}`",
        f"- **Target tolerance passed:** `{record.target_tolerance_passed}`",
        f"- **Confidence:** `{record.confidence_class.name}`",
        f"- Evidence id: `{record.evidence_id}`",
        f"- Analysis scope: `{record.analysis_scope}`",
    ]
    if record.solver_name:
        version = f" {record.solver_version}" if record.solver_version else ""
        lines.append(f"- Solver: `{record.solver_name}{version}`")
        if record.runtime_seconds is not None:
            lines.append(f"- Runtime: `{record.runtime_seconds:.1f}` s "
                         f"(return code `{record.return_code}`)")
    if record.extracted_value is not None:
        lines.append(
            f"- Extracted {record.target_quantity}: `{record.extracted_value:.6f}` "
            f"{record.extracted_unit}"
        )
        lines.append(f"- Target: `{record.target_value:.6f}` {record.target_unit}")
        if record.error_percent is not None:
            lines.append(
                f"- Error: `{record.error_percent:+.3f}%` "
                f"(tolerance `±{record.tolerance_percent:.2f}%`)"
            )
    else:
        lines.append(f"- Extracted {record.target_quantity}: **none** "
                     f"— no value was extracted from this run")
    if record.analytical_value is not None:
        model = f" ({record.analytical_model})" if record.analytical_model else ""
        lines.append(
            f"- Analytical {record.target_quantity}: `{record.analytical_value}` "
            f"{record.target_unit}{model} — an estimate, **not** a solver result"
        )
    if record.convergence is not None:
        lines.append(
            f"- Convergence: `{record.convergence.method}`, "
            f"converged: **{record.convergence.converged}**"
        )
        for note in record.convergence.notes:
            lines.append(f"  - {note}")
    if record.invalidation_reason:
        lines.append(f"- **Invalidation reason:** {record.invalidation_reason}")
    if record.superseded is not None:
        lines += [
            "",
            "### Superseded claim (audit history — not an active result)",
            "",
            f"- Withdrawn status: `{record.superseded.status}`",
            f"- Withdrawn value: `{record.superseded.extracted_value}` "
            f"{record.superseded.extracted_unit or ''}".rstrip(),
            f"- Why withdrawn: {record.superseded.why_withdrawn}",
        ]
    for gap in record.provenance_gaps:
        lines.append(f"- Provenance gap: `{gap}`")
    for gate in record.missing_scientific_validation_gates:
        lines.append(f"- Missing scientific-validation gate: `{gate}`")
    # Fabrication readiness is a *different scope* from the quantity status
    # above: an impedance can be PHYSICS_VERIFIED while the design still has no
    # DRC/LVS signoff. Label the scope, because a bare `NOT_FABRICATION_READY`
    # next to `**Status:** PHYSICS_VERIFIED` reads as a contradiction to a human
    # and, before the declared-status marker existed, to the consistency scanner.
    lines += [
        "",
        "- **Fabrication readiness:** `NOT_FABRICATION_READY` — no DRC/LVS signoff "
        "has been performed for this showcase.",
        "",
    ]
    return _block(EVIDENCE_BLOCK, "\n".join(lines))


def replace_region(text: str, start_heading: str, end_heading: str, replacement: str) -> str:
    """Replace `[start_heading, end_heading)` with `replacement`.

    Raises when either boundary is missing, so a document whose shape changed
    fails loudly instead of silently keeping a stale status section.
    """
    start = text.find(start_heading)
    if start == -1:
        raise ValueError(f"start heading not found: {start_heading!r}")
    end = text.find(end_heading, start + len(start_heading))
    if end == -1:
        raise ValueError(f"end heading not found: {end_heading!r}")
    return text[:start] + replacement.strip() + "\n\n" + text[end:]


def upsert_block(text: str, name: str, body: str) -> str:
    """Replace an existing generated block, or raise when it is absent."""
    begin = GENERATED_BEGIN.format(name=name)
    end = GENERATED_END.format(name=name)
    if begin not in text or end not in text:
        raise ValueError(f"generated block {name!r} is not present")
    head = text.split(begin, 1)[0]
    tail = text.split(end, 1)[1]
    return head + _block(name, body) + tail
