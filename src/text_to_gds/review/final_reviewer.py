"""Final aggregation reviewer.

Checks that the evidence package is structurally complete and no
placeholder or demo-only artifacts have leaked into signoff evidence.
"""

from __future__ import annotations

from typing import Any

from text_to_gds.review.base import finding, review_result

_AGENT = "final"


def _deep_contains_not_executed(value: Any, *, _depth: int = 0) -> bool:
    """Recursively search for 'NOT EXECUTED' strings in evidence values."""
    if _depth > 20:
        return False
    if isinstance(value, str):
        return "NOT EXECUTED" in value.upper()
    if isinstance(value, dict):
        return any(_deep_contains_not_executed(v, _depth=_depth + 1) for v in value.values())
    if isinstance(value, list):
        return any(_deep_contains_not_executed(v, _depth=_depth + 1) for v in value)
    return False


def review_final(evidence: dict[str, Any]) -> dict[str, Any]:
    """Final review: structural completeness and demo-guard checks."""
    findings: list[dict[str, Any]] = []

    # --- Require sidecar ---
    sidecar = evidence.get("sidecar")
    if not sidecar:
        findings.append(
            finding(
                _AGENT,
                "error",
                "Sidecar is missing from evidence. Cannot sign off without a layout manifest.",
                "Run compile_layout to produce the sidecar.",
            )
        )

    # --- Require extraction ---
    extraction = evidence.get("extraction") or evidence.get("layout_extraction")
    if not extraction:
        findings.append(
            finding(
                _AGENT,
                "error",
                "Extraction data is missing from evidence. Cannot sign off without extracted quantities.",
                "Run extract_layout to produce extraction data.",
            )
        )

    # --- visualization_only guard ---
    if isinstance(sidecar, dict):
        info = sidecar.get("info") or {}
        if info.get("visualization_only") is True:
            findings.append(
                finding(
                    _AGENT,
                    "error",
                    "Sidecar info.visualization_only is True -- this is a demo PCell not suitable for signoff.",
                    "Use a production PCell (KQCircuits / Qiskit Metal / gdsfactory) instead of a local PCell.",
                )
            )

    # --- At least one solver was EXECUTED or properly SKIPPED ---
    sim = evidence.get("simulation")
    if sim is None:
        findings.append(
            finding(
                _AGENT,
                "warning",
                "No simulation entry in evidence. At least a SKIPPED status is expected.",
                "Run or attempt a simulation, or record a proper SKIPPED status.",
            )
        )
    elif isinstance(sim, dict):
        sim_status = str(sim.get("status", "")).upper()
        if sim_status not in ("EXECUTED", "SKIPPED", "PREPARED", "FAILED"):
            findings.append(
                finding(
                    _AGENT,
                    "warning",
                    f"Simulation status is '{sim_status}' which is not a recognized status.",
                    "Use one of: EXECUTED, SKIPPED, PREPARED, FAILED.",
                )
            )

    # --- Check sub-scores if available ---
    sub_scores = evidence.get("sub_scores")
    if isinstance(sub_scores, dict) and sub_scores:
        min_score = min(sub_scores.values())
        findings.append(
            finding(
                _AGENT,
                "info",
                f"Aggregated final_score = {min_score} (min of sub-scores).",
                "",
            )
        )

    # --- Deep search for "NOT EXECUTED" strings ---
    if _deep_contains_not_executed(evidence):
        findings.append(
            finding(
                _AGENT,
                "error",
                '"NOT EXECUTED" string found in evidence values. This indicates a placeholder or broken solver run.',
                "Remove or fix the NOT EXECUTED entry before signoff.",
            )
        )

    return review_result(_AGENT, findings)
