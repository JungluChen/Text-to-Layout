"""Canonical schema for text-to-gds.extraction.v1 artifacts.

Every number in the system must trace back to exactly one of:
  1. A GDS geometry measurement (source = klayout_flattened_regions or similar)
  2. An explicit process input (source = "explicit process input")
  3. An executed solver result (source = solver name + result path)

Missing inputs produce status="failed" with an explicit reason.
No synthetic, estimated, or target-derived performance values are permitted.

This module defines:
  - SCHEMA_VERSION and physical constants
  - empty_extraction_v1() — canonical empty artifact
  - Accessor helpers that handle both old (area, ic, lj) and new (area_um2, ic_a, lj_h) field names
  - EJ/EC conversion helpers for quantum model handoffs
  - validate_extraction() — schema-level sanity checks
"""

from __future__ import annotations

import math
from typing import Any

SCHEMA_VERSION = "text-to-gds.extraction.v1"

# Every physical number must carry one of these labels.
METHOD_LABEL_GEOMETRY_EXTRACTED = "geometry_extracted"
METHOD_LABEL_ANALYTICAL = "analytical"
METHOD_LABEL_SIMULATED = "simulated"
METHOD_LABEL_MEASURED = "measured"

# Backward-compatible aliases for older callers.
METHOD_LABEL_ESTIMATED = METHOD_LABEL_ANALYTICAL
METHOD_LABEL_EXTRACTED = METHOD_LABEL_GEOMETRY_EXTRACTED
VALID_METHOD_LABELS = frozenset([
    METHOD_LABEL_GEOMETRY_EXTRACTED,
    METHOD_LABEL_ANALYTICAL,
    METHOD_LABEL_SIMULATED,
    METHOD_LABEL_MEASURED,
])

# Physical constants — never approximated or overridden by user inputs.
PHI0_WEBER = 2.067833848e-15       # Magnetic flux quantum (Wb)
ELECTRON_CHARGE_C = 1.602176634e-19  # Elementary charge (C)
PLANCK_J_S = 6.62607015e-34         # Planck constant (J·s)


def empty_extraction_v1(device: str = "") -> dict[str, Any]:
    """Return a complete empty artifact conforming to v1 schema.

    Unit-qualified field names (area_um2, ic_a, lj_h, capacitance_f, …) are
    canonical.  Legacy short names (area, ic, lj, …) in extraction.py are
    retained for backward compatibility with existing tests and consumers.
    """
    return {
        "schema": SCHEMA_VERSION,
        "status": "failed",
        "reason": "no extraction performed",
        "device": device,
        "geometry": {
            "gds_path": None,
            "sidecar_path": None,
            "layers": {},
            "ports": {},
            "bounding_boxes": {},
            "shape_count": 0,
        },
        "junction": {
            "area_um2": None,
            "jc_ua_per_um2": None,
            "ic_a": None,
            "lj_h": None,
            "lineage": {},
        },
        "linear_circuit": {
            "capacitance_f": None,
            "inductance_h": None,
            "resonance_frequency_hz": None,
            "impedance_ohm": None,
            "q_external": None,
            "lineage": {},
        },
        "solver_inputs": {
            "josephsoncircuits": {},
            "josim": {},
            "scqubits": {},
            "openems": {},
        },
        "solver_outputs": {
            "touchstone_path": None,
            "josephsoncircuits_result_path": None,
            "josim_result_path": None,
            "scqubits_result_path": None,
            "openems_result_path": None,
        },
        "validation": {
            "passed": False,
            "errors": [],
            "checks": {},
            "physical_units": True,
            "all_numbers_have_lineage": True,
        },
        "lineage": {},
    }


# ---------------------------------------------------------------------------
# Accessor helpers — read values from either old or new field names.
# ---------------------------------------------------------------------------

def _pos_float(value: Any) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) and n > 0.0 else None


def read_ic(extraction: dict[str, Any]) -> float | None:
    """Return critical current in Amperes, or None."""
    j = extraction.get("junction", {})
    return _pos_float(j.get("ic_a") if j.get("ic_a") is not None else j.get("ic"))


def read_lj(extraction: dict[str, Any]) -> float | None:
    """Return Josephson inductance in Henries, or None."""
    j = extraction.get("junction", {})
    return _pos_float(j.get("lj_h") if j.get("lj_h") is not None else j.get("lj"))


def read_capacitance(extraction: dict[str, Any]) -> float | None:
    """Return capacitance in Farads, or None."""
    lc = extraction.get("linear_circuit", {})
    return _pos_float(lc.get("capacitance_f") if lc.get("capacitance_f") is not None else lc.get("capacitance"))


def read_inductance(extraction: dict[str, Any]) -> float | None:
    """Return inductance in Henries, or None."""
    lc = extraction.get("linear_circuit", {})
    return _pos_float(lc.get("inductance_h") if lc.get("inductance_h") is not None else lc.get("inductance"))


def read_impedance(extraction: dict[str, Any]) -> float | None:
    """Return impedance in Ohms, or None."""
    lc = extraction.get("linear_circuit", {})
    return _pos_float(lc.get("impedance_ohm") if lc.get("impedance_ohm") is not None else lc.get("impedance"))


def read_q_external(extraction: dict[str, Any]) -> float | None:
    """Return external quality factor, or None."""
    return _pos_float(extraction.get("linear_circuit", {}).get("q_external"))


def has_junction_physics(extraction: dict[str, Any]) -> bool:
    """True if Ic and Lj are both present and positive."""
    return read_ic(extraction) is not None and read_lj(extraction) is not None


def has_resonator_physics(extraction: dict[str, Any]) -> bool:
    """True if L, C, and f0 are all present."""
    lc = extraction.get("linear_circuit", {})
    f0 = lc.get("resonance_frequency_hz") or lc.get("resonance_frequency")
    return all(v is not None for v in [read_inductance(extraction), read_capacitance(extraction), f0])


# ---------------------------------------------------------------------------
# EJ / EC helpers for quantum model handoffs (scqubits, etc.)
# ---------------------------------------------------------------------------

def ej_joules(ic_a: float) -> float:
    """Josephson coupling energy: EJ = Phi0 * Ic / (2 * pi)."""
    return PHI0_WEBER * ic_a / (2.0 * math.pi)


def ec_joules(capacitance_f: float) -> float:
    """Charging energy: EC = e^2 / (2 * C)."""
    return (ELECTRON_CHARGE_C ** 2) / (2.0 * capacitance_f)


def ej_ghz(ic_a: float) -> float:
    """Josephson energy in GHz (EJ / h)."""
    return ej_joules(ic_a) / (PLANCK_J_S * 1e9)


def ec_ghz(capacitance_f: float) -> float:
    """Charging energy in GHz (EC / h)."""
    return ec_joules(capacitance_f) / (PLANCK_J_S * 1e9)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def validate_extraction(extraction: dict[str, Any]) -> list[str]:
    """Return a list of schema violations (empty = valid)."""
    errors: list[str] = []
    schema = extraction.get("schema")
    if schema not in (SCHEMA_VERSION, "text-to-gds.extraction.v0"):
        errors.append(f"unexpected schema: {schema!r}")
    if not extraction.get("device"):
        errors.append("missing device identifier")
    if extraction.get("status") not in ("ok", "failed"):
        errors.append("status must be 'ok' or 'failed'")
    errors.extend(validate_method_labels(extraction))
    return errors


def validate_method_labels(extraction: dict[str, Any]) -> list[str]:
    """Check that every lineage entry carries a valid method_label.

    Violations mean a value could be silently misrepresented — estimated
    results labeled as simulated, etc.  Returns a list of error strings.
    """
    errors: list[str] = []
    lineage = extraction.get("lineage", {})
    for key, entry in lineage.items():
        if not isinstance(entry, dict):
            continue
        label = entry.get("method_label")
        if label is None:
            errors.append(f"lineage['{key}'] missing method_label")
        elif label not in VALID_METHOD_LABELS:
            errors.append(
                f"lineage['{key}'] has invalid method_label {label!r}; "
                f"must be one of {sorted(VALID_METHOD_LABELS)}"
            )
    return errors
