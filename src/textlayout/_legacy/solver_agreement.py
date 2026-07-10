"""Solver Agreement Engine.

Never trust a single solver. This module cross-checks a physical quantity
(frequency, Q, impedance, capacitance, ...) computed by two or more independent
sources -- ideally at least two open EM solvers plus an analytical model -- and
emits a deterministic confidence score with an explicit PASS/FAIL threshold.

The confidence model is intentionally simple and monotone:

    reference          = median of the reported values
    max_relative_error = max |value - reference| / |reference|
    passed             = max_relative_error <= tolerance
    confidence_pct     = 100 * (1 - min(1, max_relative_error / (2 * tolerance)))

so confidence is 100% at perfect agreement, 50% at exactly the tolerance
boundary (the worst still-passing case), and 0% at twice the tolerance. A single
source can never produce a non-zero confidence: agreement requires corroboration.
"""

from __future__ import annotations

from statistics import median
from typing import Any


def cross_validate(
    sources: list[dict[str, Any]],
    *,
    quantity: str = "value",
    tolerance_pct: float = 5.0,
) -> dict[str, Any]:
    """Cross-validate one quantity across independent solver/theory sources.

    ``sources`` is a list of ``{"source": str, "value": float}`` entries (extra
    keys are ignored). Entries whose value is ``None`` are treated as a source
    that did not produce a result and are excluded from the comparison.
    """
    if tolerance_pct <= 0.0:
        raise ValueError(f"tolerance_pct must be positive, got {tolerance_pct}")

    usable = [s for s in sources if s.get("value") is not None]
    values = [float(s["value"]) for s in usable]

    if len(usable) < 2:
        return {
            "schema": "text-to-gds.solver-agreement.v1",
            "quantity": quantity,
            "tolerance_pct": tolerance_pct,
            "n_sources": len(usable),
            "sources": [
                {"source": str(s.get("source", "unknown")), "value": s.get("value")}
                for s in usable
            ],
            "reference_value": values[0] if values else None,
            "max_relative_error_pct": None,
            "passed": False,
            "confidence_pct": 0.0,
            "verdict": "insufficient_sources",
            "reason": "agreement requires at least two independent sources; never trust one solver",
        }

    reference = float(median(values))
    if reference == 0.0:
        # Fall back to mean magnitude to avoid division by zero.
        reference = sum(abs(v) for v in values) / len(values) or 1.0

    tolerance = tolerance_pct / 100.0
    detailed = []
    max_rel = 0.0
    for s in usable:
        value = float(s["value"])
        rel = abs(value - reference) / abs(reference)
        max_rel = max(max_rel, rel)
        detailed.append(
            {
                "source": str(s.get("source", "unknown")),
                "value": value,
                "relative_error_pct": round(rel * 100.0, 4),
            }
        )

    passed = max_rel <= tolerance
    confidence = 100.0 * (1.0 - min(1.0, max_rel / (2.0 * tolerance)))
    return {
        "schema": "text-to-gds.solver-agreement.v1",
        "quantity": quantity,
        "tolerance_pct": tolerance_pct,
        "n_sources": len(usable),
        "sources": detailed,
        "reference_value": reference,
        "max_relative_error_pct": round(max_rel * 100.0, 4),
        "passed": passed,
        "confidence_pct": round(confidence, 1),
        "verdict": "agree" if passed else "disagree",
    }


def cross_validate_solvers(
    touchstone_a: "str | None",
    touchstone_b: "str | None",
    *,
    tolerance_pct: float = 5.0,
) -> dict[str, Any]:
    """Cross-validate two Touchstone files (e.g. openEMS vs HFSS).

    Returns status="failed" if fewer than two executed solver outputs are
    supplied.  If both exist, compares S11 magnitude at the first frequency
    point using cross_validate().

    Parameters
    ----------
    touchstone_a, touchstone_b:
        Paths to .s1p or .s2p files, or None for solvers that did not run.
    tolerance_pct:
        Relative agreement threshold (default 5 %).

    Returns
    -------
    dict with status, passed, confidence_pct, and reason fields.
    """
    from pathlib import Path

    missing = [label for label, p in [("A", touchstone_a), ("B", touchstone_b)] if p is None]
    if missing:
        reason = (
            f"solver output(s) not executed: {', '.join(missing)} — "
            "cross-validation requires both solvers to have run"
        )
        return {
            "schema": "text-to-gds.solver-agreement.v1",
            "status": "failed",
            "passed": False,
            "confidence_pct": 0.0,
            "reason": reason,
        }

    def _read_s11_db(path: str | Path) -> float:
        """Return |S11| at first data frequency, parsed from Touchstone."""
        import math
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("!") or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) >= 3:
                try:
                    re_val = float(parts[1])
                    im_val = float(parts[2])
                    return math.sqrt(re_val ** 2 + im_val ** 2)
                except ValueError:
                    continue
        return 1.0

    val_a = _read_s11_db(touchstone_a)
    val_b = _read_s11_db(touchstone_b)

    result = cross_validate(
        [
            {"source": str(touchstone_a), "value": val_a},
            {"source": str(touchstone_b), "value": val_b},
        ],
        quantity="|S11|",
        tolerance_pct=tolerance_pct,
    )
    result["status"] = "ok" if result["passed"] else "failed"
    if not result["passed"]:
        result.setdefault(
            "reason",
            f"solvers disagree by {result['max_relative_error_pct']:.1f}% > {tolerance_pct}%",
        )
    return result


def cross_validate_with_disagreement(
    sources: list[dict[str, Any]],
    *,
    quantity: str = "value",
    tolerance_pct: float = 5.0,
) -> dict[str, Any]:
    """Like cross_validate() but also surfaces mesh_convergence and boundary_conditions.

    Each source dict may contain extra metadata keys (mesh_convergence,
    boundary_conditions, etc.) alongside the mandatory ``source`` and
    ``value`` keys.  These are aggregated into the result so reviewers can
    inspect solver-level quality without re-reading each source dict.
    """
    result = cross_validate(sources, quantity=quantity, tolerance_pct=tolerance_pct)

    mesh_entries = [s["mesh_convergence"] for s in sources if "mesh_convergence" in s]
    bc_entries = [s["boundary_conditions"] for s in sources if "boundary_conditions" in s]

    result["mesh_convergence"] = mesh_entries if len(mesh_entries) > 1 else (mesh_entries[0] if mesh_entries else None)
    result["boundary_conditions"] = bc_entries if len(bc_entries) > 1 else (bc_entries[0] if bc_entries else None)
    return result
