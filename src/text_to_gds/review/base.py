"""Shared finding/result helpers for the review committee."""

from __future__ import annotations

from typing import Any

SEVERITY_PENALTY = {"error": 40, "warning": 10, "info": 0}


def finding(agent: str, severity: str, message: str, recommendation: str = "") -> dict[str, Any]:
    if severity not in SEVERITY_PENALTY:
        raise ValueError(f"Unknown severity '{severity}'")
    return {
        "agent": agent,
        "severity": severity,
        "finding": message,
        "recommendation": recommendation,
    }


def score_from_findings(findings: list[dict[str, Any]]) -> int:
    """Start at 100 and subtract a penalty per finding; clamp to [0, 100]."""
    penalty = sum(SEVERITY_PENALTY[f["severity"]] for f in findings)
    return max(0, min(100, 100 - penalty))


def review_result(agent: str, findings: list[dict[str, Any]]) -> dict[str, Any]:
    has_error = any(f["severity"] == "error" for f in findings)
    return {
        "agent": agent,
        "passed": not has_error,
        "score": score_from_findings(findings),
        "findings": findings,
    }


def device_text(evidence: dict[str, Any]) -> str:
    sidecar = evidence.get("sidecar") or {}
    info = sidecar.get("info") or {}
    device = evidence.get("device") or sidecar.get("pcell") or ""
    return f"{device} {info.get('device_type', '')}".lower()


def port_names(evidence: dict[str, Any]) -> list[str]:
    sidecar = evidence.get("sidecar") or {}
    names = []
    for port in sidecar.get("ports") or []:
        if isinstance(port, dict) and port.get("name"):
            names.append(str(port["name"]).lower())
    return names
