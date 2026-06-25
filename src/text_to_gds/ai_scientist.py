"""AI scientist orchestration -- "here is a layout proven to work".

Ties the pipeline together:

    feasibility gate -> (generate candidate) -> review committee -> readiness

``assess_design`` is the pure, testable core: given a device, its targets, and
the evidence from a generated candidate, it runs the feasibility gate, the review
committee, and the readiness score, and returns a single accept/reject verdict.
Generation/solving is injected by the caller (the MCP ``run_ai_scientist`` tool
wires it to the local open-source workflow), so this module stays solver- and
network-free.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from text_to_gds.feasibility_gate import check_design_feasibility
from text_to_gds.research_readiness import research_readiness
from text_to_gds.review.committee import review_committee


def assess_design(
    device: str,
    targets: dict[str, Any],
    evidence: dict[str, Any],
    *,
    solver_agreement: dict[str, Any] | None = None,
    device_id: str = "",
) -> dict[str, Any]:
    """Run feasibility -> committee -> readiness over a generated candidate."""
    feasibility = check_design_feasibility(device, targets, device_id=device_id)
    if not feasibility["accepted"]:
        return {
            "schema": "text-to-gds.ai-scientist.v1",
            "device": device,
            "stage": "feasibility",
            "accepted": False,
            "verdict": "rejected_infeasible",
            "feasibility": feasibility,
            "committee": None,
            "readiness": None,
            "summary": "Rejected before layout: the specification is not physically realisable.",
        }

    committee = review_committee(evidence)
    readiness = research_readiness(
        committee, feasibility=feasibility, solver_agreement=solver_agreement
    )
    accepted = feasibility["accepted"] and committee["approved"] and readiness["ready"]
    return {
        "schema": "text-to-gds.ai-scientist.v1",
        "device": device,
        "stage": "review",
        "accepted": accepted,
        "verdict": "validated" if accepted else "needs_revision",
        "feasibility": feasibility,
        "committee": committee,
        "readiness": readiness,
        "summary": (
            "Layout validated: feasible, reviewed, and above the readiness threshold."
            if accepted
            else "Layout generated but not yet validated; see committee blockers and readiness axes."
        ),
    }


def write_review_report(assessment: dict[str, Any], report_path: str | Path) -> dict[str, Any]:
    """Render a Markdown review report from an ``assess_design`` result."""
    lines = [
        f"# Design Review Report -- {assessment['device']}",
        "",
        f"**Verdict:** {assessment['verdict']}  ",
        f"**Accepted:** {assessment['accepted']}",
        "",
        "## Feasibility gate",
    ]
    feas = assessment.get("feasibility") or {}
    lines.append(f"- Verdict: {feas.get('verdict', 'n/a')}")
    for blocker in feas.get("blockers", []):
        lines.append(f"  - blocker: {blocker}")

    committee = assessment.get("committee")
    if committee:
        lines += ["", "## Review committee", f"- Approved: {committee['approved']}",
                  f"- Score (min across reviewers): {committee['score']}",
                  f"- Errors: {committee['error_count']}, warnings: {committee['warning_count']}", ""]
        for review in committee["reviews"]:
            lines.append(f"### {review['agent']} -- score {review['score']} ({'pass' if review['passed'] else 'FAIL'})")
            for f in review["findings"]:
                lines.append(f"- [{f['severity']}] {f['finding']}")
                if f["recommendation"]:
                    lines.append(f"  - fix: {f['recommendation']}")
            lines.append("")

    readiness = assessment.get("readiness")
    if readiness:
        lines += ["## Research readiness", f"- Aggregate: {readiness['aggregate']} (ready={readiness['ready']})"]
        for name, axis in readiness["axes"].items():
            lines.append(f"  - {name}: {axis['score']} ({'pass' if axis['passed'] else 'fail'})")

    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"schema": "text-to-gds.review-report.v1", "report_path": str(report), "accepted": assessment["accepted"]}


def diagnose_and_repair(
    target: dict[str, Any],
    actual: dict[str, Any],
    evidence: dict[str, Any],
    *,
    repair_gds_path: str | Path | None = None,
) -> dict[str, Any]:
    """Diagnose a device mismatch and optionally regenerate a repaired JPA layout."""
    target_frequency = target.get("frequency_ghz")
    actual_frequency = actual.get("frequency_ghz") or actual.get("center_frequency_ghz")
    diagnosis: dict[str, Any] = {
        "schema": "text-to-gds.ai-scientist-diagnosis.v1",
        "status": "diagnosed",
        "target": target,
        "actual": actual,
        "evidence": evidence,
        "reason": None,
        "repair": None,
    }
    if target_frequency and actual_frequency:
        ratio = float(target_frequency) / float(actual_frequency)
        if actual_frequency < target_frequency:
            capacitance_scale = 1.0 / (ratio * ratio)
            shorten_pct = max(0.0, (1.0 - capacitance_scale) * 100.0)
            diagnosis["reason"] = "capacitance too large"
            diagnosis["repair"] = {
                "action": "shorten IDC/shunt capacitor finger length",
                "percentage": shorten_pct,
                "capacitance_scale": capacitance_scale,
            }
        elif actual_frequency > target_frequency:
            capacitance_scale = 1.0 / (ratio * ratio)
            lengthen_pct = max(0.0, (capacitance_scale - 1.0) * 100.0)
            diagnosis["reason"] = "capacitance too small"
            diagnosis["repair"] = {
                "action": "lengthen IDC/shunt capacitor finger length",
                "percentage": lengthen_pct,
                "capacitance_scale": capacitance_scale,
            }
    if diagnosis["repair"] is None:
        diagnosis["status"] = "needs_more_evidence"
        diagnosis["reason"] = "target and actual frequency are required for automatic repair"
        return diagnosis

    if repair_gds_path is not None:
        from text_to_gds.pcells import lumped_element_jpa_seed

        scale = float(diagnosis["repair"]["capacitance_scale"])
        params = {
            "center_frequency_ghz": float(target_frequency),
            "target_gain_db": float(target.get("gain_db", 20.0)),
            "target_bandwidth_mhz": float(target.get("bandwidth_mhz", 100.0)),
            "shunt_capacitor_width_um": max(float(evidence.get("shunt_capacitor_width_um", 70.0)) * scale, 1.0),
            "coupling_capacitor_length_um": max(float(evidence.get("coupling_capacitor_length_um", 42.0)) * scale, 1.0),
        }
        component = lumped_element_jpa_seed(**params)
        path = Path(repair_gds_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        component.write_gds(str(path))
        sidecar_path = path.with_suffix(".repair.sidecar.json")
        sidecar_path.write_text(
            json.dumps({"pcell": "lumped_element_jpa_seed", "gds_path": str(path), "info": dict(component.info)}, indent=2),
            encoding="utf-8",
        )
        diagnosis["repair"]["regenerated_gds_path"] = str(path)
        diagnosis["repair"]["sidecar_path"] = str(sidecar_path)
    return diagnosis
