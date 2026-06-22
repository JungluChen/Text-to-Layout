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
