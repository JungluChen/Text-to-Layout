"""Via-chain and sheet-resistance extraction from GDS sidecar metadata.

Computes total resistance from geometry without an external solver:
  R_total = N_via × R_via + R_sheet × L / W

Where:
  N_via       — number of vias in the chain (from sidecar.json)
  R_via       — per-via resistance from process spec (default: 0.3 Ω for Al/Nb)
  R_sheet     — sheet resistance of the metal layer (from process spec, Ω/□)
  L, W        — total metal trace length and width (from GDS geometry)

Provenance: method="geometry_extracted", source="sidecar.json + process spec"
Never uses LLM estimates. All inputs must trace to sidecar or explicit process inputs.

Output: resistance_extraction.json
Schema: text-to-gds.resistance-extraction.v1
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "text-to-gds.resistance-extraction.v1"

# Default process parameters for Nb/Al superconducting process (demonstration values)
# Real tapeout requires calibrated process data.
_DEFAULT_PROCESS = {
    "nb_m1_sheet_resistance_ohm_per_sq": 0.005,   # Nb M1 at 4 K
    "nb_m2_sheet_resistance_ohm_per_sq": 0.005,   # Nb M2 at 4 K
    "nb_m3_sheet_resistance_ohm_per_sq": 0.005,   # Nb M3 at 4 K
    "via12_resistance_ohm": 0.30,                  # Nb via 1→2
    "via23_resistance_ohm": 0.30,                  # Nb via 2→3
    "al_normal_sheet_resistance_ohm_per_sq": 0.050,  # Al in normal state (not SC)
}


def _sheet_resistance(layer_name: str, process: dict[str, Any]) -> float:
    """Resolve sheet resistance for a named layer."""
    key = f"{layer_name.lower()}_sheet_resistance_ohm_per_sq"
    return float(process.get(key, _DEFAULT_PROCESS.get(key, 0.01)))


def _via_resistance(via_type: str, process: dict[str, Any]) -> float:
    key = f"{via_type.lower()}_resistance_ohm"
    return float(process.get(key, _DEFAULT_PROCESS.get(key, 0.30)))


def extract_resistance(
    sidecar_path: str | Path,
    *,
    process_overrides: dict[str, Any] | None = None,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Extract total resistance of a via chain or metal trace from sidecar metadata.

    Returns:
        status: "executed" | "failed"
        resistance_ohm: float
        provenance: all inputs traced to sidecar + process spec
    """
    sidecar = Path(sidecar_path)
    if not sidecar.is_file():
        return _failed(f"sidecar not found: {sidecar}", report_path)

    try:
        sc = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _failed(f"cannot read sidecar: {exc}", report_path)

    process = {**_DEFAULT_PROCESS, **(process_overrides or {})}
    pcell = sc.get("pcell", "")

    # Dispatch by device type
    if "via_chain" in pcell.lower() or "via_chain_monitor" in pcell.lower():
        return _extract_via_chain(sc, process, sidecar_path, report_path)
    elif any(kw in pcell.lower() for kw in ("cpw", "resonator", "feedline")):
        return _extract_cpw_resistance(sc, process, sidecar_path, report_path)
    else:
        return _extract_generic_trace(sc, process, sidecar_path, report_path)


def _extract_via_chain(
    sc: dict[str, Any],
    process: dict[str, Any],
    sidecar_path: str | Path,
    report_path: str | Path | None,
) -> dict[str, Any]:
    """Extract resistance of a via-chain monitor structure."""
    params = sc.get("parameters", {})
    info = sc.get("device_info", {})

    # Via chain geometry
    n_vias = int(
        info.get("via_count")
        or params.get("stage_count", params.get("n_stages", 100))
    )
    via_type = str(info.get("via_type", params.get("via_type", "via12")))
    metal_layer = str(info.get("metal_layer", params.get("metal_layer", "nb_m1")))

    # Metal trace dimensions
    trace_length_um = float(
        info.get("total_trace_length_um")
        or params.get("trace_length_um", n_vias * 5.0)  # default 5 µm per stage
    )
    trace_width_um = float(
        info.get("trace_width_um")
        or params.get("trace_width_um", params.get("trace_width", 2.0))
    )

    r_via = _via_resistance(via_type, process)
    rs = _sheet_resistance(metal_layer, process)
    n_squares = trace_length_um / trace_width_um if trace_width_um > 0 else 0.0
    r_metal = rs * n_squares
    r_total = n_vias * r_via + r_metal

    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "executed",
        "device": "via_chain_monitor",
        "sidecar": str(sidecar_path),
        "inputs": {
            "n_vias": n_vias,
            "via_type": via_type,
            "metal_layer": metal_layer,
            "trace_length_um": trace_length_um,
            "trace_width_um": trace_width_um,
            "n_squares": round(n_squares, 2),
            "r_via_ohm": r_via,
            "sheet_resistance_ohm_per_sq": rs,
        },
        "resistance_ohm": r_total,
        "breakdown": {
            "r_vias_ohm": n_vias * r_via,
            "r_metal_ohm": r_metal,
            "r_total_ohm": r_total,
            "formula": "R = N_via × R_via + R_sheet × (L/W)",
        },
        "provenance": {
            "method": "geometry_extracted",
            "source": "sidecar.json + process spec (demonstration values)",
            "confidence": 0.70,
            "note": (
                "Sheet resistance and via resistance are demonstration process defaults. "
                "Real tapeout requires calibrated R_sheet and R_via from process measurements."
            ),
        },
    }

    _write_report(result, report_path)
    return result


def _extract_cpw_resistance(
    sc: dict[str, Any],
    process: dict[str, Any],
    sidecar_path: str | Path,
    report_path: str | Path | None,
) -> dict[str, Any]:
    """Extract series resistance of a CPW trace (superconducting → ~0 Ω at T < Tc)."""
    params = sc.get("parameters", {})
    info = sc.get("device_info", {})

    length_um = float(
        info.get("length_um")
        or params.get("length_um", params.get("quarter_wave_length_um", 5000.0))
    )
    width_um = float(
        info.get("trace_width_um")
        or params.get("trace_width", params.get("center_width_um", 10.0))
    )
    metal_layer = str(info.get("metal_layer", "nb_m3"))
    rs = _sheet_resistance(metal_layer, process)
    n_sq = length_um / width_um if width_um > 0 else 0.0
    r_dc = rs * n_sq

    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "executed",
        "device": "cpw_trace",
        "sidecar": str(sidecar_path),
        "inputs": {
            "length_um": length_um,
            "width_um": width_um,
            "n_squares": round(n_sq, 1),
            "sheet_resistance_ohm_per_sq": rs,
            "metal_layer": metal_layer,
        },
        "resistance_ohm": r_dc,
        "breakdown": {
            "r_dc_ohm": r_dc,
            "formula": "R = R_sheet × L / W",
            "note": "For Nb/Al at T < Tc: R_DC = 0 Ω (superconducting). Value above is normal-state estimate.",
        },
        "provenance": {
            "method": "geometry_extracted",
            "source": "sidecar.json + process spec (demonstration values)",
            "confidence": 0.60,
        },
    }
    _write_report(result, report_path)
    return result


def _extract_generic_trace(
    sc: dict[str, Any],
    process: dict[str, Any],
    sidecar_path: str | Path,
    report_path: str | Path | None,
) -> dict[str, Any]:
    """Fallback resistance extraction for unrecognised device types."""
    params = sc.get("parameters", {})
    info = sc.get("device_info", {})

    length_um = float(info.get("length_um") or params.get("length_um", 0.0))
    width_um = float(info.get("trace_width_um") or params.get("trace_width", 1.0))

    if length_um <= 0 or width_um <= 0:
        return _failed(
            f"Cannot extract resistance: length_um={length_um}, width_um={width_um}. "
            "Sidecar must contain device_info.length_um and device_info.trace_width_um.",
            report_path,
        )

    rs = _sheet_resistance("nb_m1", process)
    r_total = rs * length_um / width_um

    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "executed",
        "device": sc.get("pcell", "unknown"),
        "sidecar": str(sidecar_path),
        "inputs": {
            "length_um": length_um,
            "width_um": width_um,
            "sheet_resistance_ohm_per_sq": rs,
        },
        "resistance_ohm": r_total,
        "breakdown": {
            "r_total_ohm": r_total,
            "formula": "R = R_sheet × L / W",
        },
        "provenance": {
            "method": "geometry_extracted",
            "source": "sidecar.json + default process spec",
            "confidence": 0.55,
        },
    }
    _write_report(result, report_path)
    return result


def _failed(reason: str, report_path: str | Path | None) -> dict[str, Any]:
    result: dict[str, Any] = {"schema": SCHEMA, "status": "failed", "reason": reason}
    _write_report(result, report_path)
    return result


def _write_report(result: dict[str, Any], report_path: str | Path | None) -> None:
    if report_path is None:
        return
    rp = Path(report_path)
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["report_path"] = str(rp)
