"""Solver agreement validation — Phase 6.

Extends solver_agreement.py with device-specific multi-source comparison
and auto-trigger for the repair loop when disagreement exceeds threshold.

Never trust one solver. Every physical claim requires corroboration from
at least two independent sources (analytical + solver, or two solvers).

If disagreement > threshold → flag for auto-repair.
"""

from __future__ import annotations

import math
from statistics import median, stdev
from typing import Any

from text_to_gds.solver_agreement import cross_validate

_SCHEMA = "text-to-gds.solver-agreement-v2.v1"

# Default per-quantity tolerances (%)
_DEFAULT_TOLERANCES: dict[str, float] = {
    "capacitance_pf": 5.0,
    "impedance_ohm": 3.0,
    "frequency_ghz": 1.0,
    "inductance_ph": 5.0,
    "gain_db": 2.0,
    "q_factor": 10.0,
    "anharmonicity_mhz": 5.0,
}


def validate_solver_agreement(
    quantity_name: str,
    sources: list[dict[str, Any]],
    *,
    tolerance_pct: float | None = None,
    trigger_repair: bool = True,
) -> dict[str, Any]:
    """Validate agreement across multiple solver sources for one quantity.

    Parameters
    ----------
    quantity_name : str
        Name of the physical quantity (e.g. "capacitance_pf", "impedance_ohm").
    sources : list[dict]
        Each entry must have: {"source": str, "value": float | None, "unit": str}.
        None values = solver unavailable (excluded from comparison).
    tolerance_pct : float | None
        Override default tolerance. If None, use _DEFAULT_TOLERANCES.
    trigger_repair : bool
        If True and agreement fails, add "repair_required": True to the output.

    Returns
    -------
    dict with:
        passed: bool
        confidence_pct: float
        verdict: "agree" | "disagree" | "insufficient_sources"
        sources: list of source-level results
        repair_required: bool (if trigger_repair=True and not passed)
        recommendation: str (what to do if disagreement detected)
    """
    tol = tolerance_pct
    if tol is None:
        tol = _DEFAULT_TOLERANCES.get(quantity_name, 5.0)

    result = cross_validate(sources, quantity=quantity_name, tolerance_pct=tol)
    result["schema"] = _SCHEMA
    result["quantity_name"] = quantity_name

    if not result["passed"] and trigger_repair:
        result["repair_required"] = True
        result["recommendation"] = _repair_recommendation(
            quantity_name, result.get("sources", [])
        )
    else:
        result["repair_required"] = False

    # Add statistical summary if ≥ 3 sources
    usable = [s for s in sources if s.get("value") is not None]
    if len(usable) >= 3:
        values = [float(s["value"]) for s in usable]
        result["statistics"] = {
            "mean": round(sum(values) / len(values), 6),
            "std_dev": round(stdev(values), 6) if len(values) > 1 else 0.0,
            "cv_pct": round(
                stdev(values) / max(abs(sum(values) / len(values)), 1e-12) * 100.0, 3
            ) if len(values) > 1 else 0.0,
        }

    return result


def _repair_recommendation(quantity: str, sources: list[dict[str, Any]]) -> str:
    """Generate a physics-based repair recommendation for a disagreement."""
    recs = {
        "capacitance_pf": (
            "Disagreement in capacitance. Check: (1) IDC finger dimensions in GDS, "
            "(2) substrate permittivity in process.yaml, (3) fringe capacitance model. "
            "Increase finger overlap length or reduce finger gap to increase capacitance."
        ),
        "impedance_ohm": (
            "CPW impedance mismatch. Check: (1) center_width_um and gap_um in GDS, "
            "(2) substrate permittivity and thickness in process.yaml. "
            "To increase Z0: decrease width or increase gap. "
            "To decrease Z0: increase width or decrease gap."
        ),
        "frequency_ghz": (
            "Resonant frequency disagreement. Check: (1) resonator length in GDS, "
            "(2) effective permittivity from CPW model, "
            "(3) loading capacitance from coupling IDC. "
            "To increase f0: decrease resonator length."
        ),
        "inductance_ph": (
            "Inductance disagreement. Check: (1) junction area in GDS, "
            "(2) critical current density Jc in process.yaml. "
            "Larger junction area → smaller Lj. Smaller area → larger Lj."
        ),
        "gain_db": (
            "JPA gain disagreement. Check: (1) Lj from junction area, "
            "(2) coupling capacitance, (3) pump power and frequency. "
            "Run full JosephsonCircuits.jl sweep to find optimal pump power."
        ),
    }
    return recs.get(quantity, (
        f"Disagreement in {quantity}. Investigate all solver inputs and "
        "verify geometry parameters against the GDS extraction."
    ))


def validate_cpw_agreement(
    *,
    analytical_z0: float,
    em_z0: float | None = None,
    analytical_source: str = "conformal_mapping",
    em_source: str = "openEMS_FDTD",
    tolerance_pct: float = 5.0,
) -> dict[str, Any]:
    """Compare analytical CPW Z0 vs EM solver Z0."""
    sources = [
        {"source": analytical_source, "value": analytical_z0, "unit": "Ohm"},
    ]
    if em_z0 is not None:
        sources.append({"source": em_source, "value": em_z0, "unit": "Ohm"})

    result = validate_solver_agreement(
        "impedance_ohm",
        sources,
        tolerance_pct=tolerance_pct,
    )
    result["example"] = {
        f"analytical_{analytical_source}_ohm": round(analytical_z0, 3),
        f"em_{em_source}_ohm": round(em_z0, 3) if em_z0 is not None else "SKIPPED",
        "error_pct": round(
            abs(analytical_z0 - em_z0) / max(abs(analytical_z0), 1e-9) * 100.0, 3
        ) if em_z0 is not None else None,
    }
    return result


def validate_capacitance_agreement(
    *,
    analytical_pf: float | None = None,
    fastcap_pf: float | None = None,
    elmer_pf: float | None = None,
    tolerance_pct: float = 5.0,
) -> dict[str, Any]:
    """Cross-validate capacitance from analytical formula, FastCap, and Elmer."""
    sources: list[dict[str, Any]] = []
    if analytical_pf is not None:
        sources.append({"source": "analytical_IDC", "value": analytical_pf, "unit": "pF"})
    if fastcap_pf is not None:
        sources.append({"source": "FastCap_BEM", "value": fastcap_pf, "unit": "pF"})
    if elmer_pf is not None:
        sources.append({"source": "ElmerFEM", "value": elmer_pf, "unit": "pF"})

    return validate_solver_agreement(
        "capacitance_pf",
        sources,
        tolerance_pct=tolerance_pct,
    )


def validate_frequency_agreement(
    *,
    analytical_ghz: float | None = None,
    openems_ghz: float | None = None,
    palace_ghz: float | None = None,
    scqubits_ghz: float | None = None,
    tolerance_pct: float = 1.0,
) -> dict[str, Any]:
    """Cross-validate resonant frequency from multiple sources."""
    sources: list[dict[str, Any]] = []
    if analytical_ghz is not None:
        sources.append({"source": "analytical_transmission_line", "value": analytical_ghz, "unit": "GHz"})
    if openems_ghz is not None:
        sources.append({"source": "openEMS_FDTD", "value": openems_ghz, "unit": "GHz"})
    if palace_ghz is not None:
        sources.append({"source": "Palace_FEM", "value": palace_ghz, "unit": "GHz"})
    if scqubits_ghz is not None:
        sources.append({"source": "scqubits", "value": scqubits_ghz, "unit": "GHz"})

    return validate_solver_agreement(
        "frequency_ghz",
        sources,
        tolerance_pct=tolerance_pct,
    )


def full_multi_source_report(
    quantities: dict[str, dict[str, Any]],
    *,
    tolerance_overrides: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Run agreement validation on multiple quantities and produce a report.

    Parameters
    ----------
    quantities : dict
        Map of quantity_name → {"sources": [...], "unit": str}.
    tolerance_overrides : dict | None
        Override default tolerances per quantity.

    Returns
    -------
    dict with per-quantity results and overall pass/fail summary.
    """
    overrides = tolerance_overrides or {}
    results: dict[str, Any] = {}
    all_passed = True
    any_insufficient = False
    repair_needed: list[str] = []

    for qname, qdata in quantities.items():
        tol = overrides.get(qname)
        result = validate_solver_agreement(
            qname,
            qdata.get("sources", []),
            tolerance_pct=tol,
        )
        results[qname] = result
        if result.get("verdict") == "insufficient_sources":
            any_insufficient = True
        elif not result["passed"]:
            all_passed = False
            if result.get("repair_required"):
                repair_needed.append(qname)

    return {
        "schema": "text-to-gds.multi-source-report.v1",
        "quantities": results,
        "summary": {
            "all_passed": all_passed,
            "any_insufficient": any_insufficient,
            "repair_required": bool(repair_needed),
            "quantities_needing_repair": repair_needed,
        },
    }
