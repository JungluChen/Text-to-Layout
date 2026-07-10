"""Microwave reviewer: S-parameter passivity, reciprocity, ports."""

from __future__ import annotations

from typing import Any

from textlayout._legacy.review.base import device_text, finding, port_names, review_result

_AGENT = "microwave"


def _scalar_db(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        values = [float(v) for v in value if v is not None]
        return max(values) if values else None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _lin(db: float | None) -> float | None:
    return 10.0 ** (db / 20.0) if db is not None else None


def review_microwave(evidence: dict[str, Any]) -> dict[str, Any]:
    sim = evidence.get("simulation") or {}
    performance = sim.get("physical_performance") or {}
    sparams = sim.get("s_parameters_db") or performance.get("s_parameters_db") or {}
    text = device_text(evidence)
    is_active = any(k in text for k in ("jpa", "twpa", "amplifier", "paramp"))
    findings: list[dict[str, Any]] = []

    if len(port_names(evidence)) < 2:
        findings.append(
            finding(_AGENT, "error", "A microwave network needs at least two ports.",
                    "Add a second port to define an S-matrix.")
        )

    if not sparams:
        findings.append(finding(_AGENT, "info", "No S-parameters available to check passivity.", ""))
    elif is_active:
        findings.append(
            finding(_AGENT, "info",
                    "Active device (parametric amplifier): passivity bound |S|^2<=1 is not applicable.",
                    "Verify gain against the harmonic-balance model instead.")
        )
    else:
        s11 = _lin(_scalar_db(sparams.get("s11_db")))
        s21 = _lin(_scalar_db(sparams.get("s21_db")))
        if s11 is not None and s21 is not None:
            total = s11 ** 2 + s21 ** 2
            if total > 1.0 + 1e-3:
                findings.append(
                    finding(_AGENT, "error",
                            f"Passivity violated: |S11|^2+|S21|^2 = {total:.3f} > 1 for a passive device.",
                            "Check port de-embedding and boundary conditions.")
                )
        s12_db = _scalar_db(sparams.get("s12_db"))
        s21_db = _scalar_db(sparams.get("s21_db"))
        if s12_db is not None and s21_db is not None and abs(s12_db - s21_db) > 1.0:
            findings.append(
                finding(_AGENT, "warning",
                        "S21 != S12 without a nonreciprocal element; reciprocity expected.",
                        "Verify the model or document the nonreciprocal element.")
            )

    return review_result(_AGENT, findings)
