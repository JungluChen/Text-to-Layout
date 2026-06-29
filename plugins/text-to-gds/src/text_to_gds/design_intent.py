"""Requirement parsing and circuit synthesis before any GDS generation."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from text_to_gds.cpw_physics import synthesize_cpw
from text_to_gds.extraction import PHI0_WEBER


def _number(prompt: str, unit: str) -> float | None:
    match = re.search(rf"(\d+(?:\.\d+)?)\s*{unit}\b", prompt, flags=re.IGNORECASE)
    return float(match.group(1)) if match else None


def _device(prompt: str) -> str:
    text = prompt.lower()
    if "jpa" in text or "parametric amplifier" in text:
        return "JPA"
    if "transmon" in text or "qubit" in text:
        return "transmon"
    if "resonator" in text:
        return "CPW_resonator"
    if "squid" in text:
        return "SQUID"
    if "junction" in text or re.search(r"\bjj\b", text):
        return "Josephson_junction"
    return "unknown"


def synthesize_design_intent(
    prompt: str,
    *,
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse requirements and solve traceable pre-layout circuit quantities."""
    supplied = dict(inputs or {})
    device = str(supplied.get("device") or _device(prompt))
    frequency_ghz = supplied.get("frequency_ghz") or _number(prompt, "ghz")
    gain_db = supplied.get("gain_db") or _number(prompt, "db")
    bandwidth_mhz = supplied.get("bandwidth_mhz") or _number(prompt, "mhz")
    target = {
        "frequency_ghz": float(frequency_ghz) if frequency_ghz is not None else None,
        "gain_db": float(gain_db) if gain_db is not None else None,
        "bandwidth_mhz": float(bandwidth_mhz) if bandwidth_mhz is not None else None,
        "impedance_ohm": float(supplied.get("target_impedance_ohm", 50.0)),
    }
    blockers: list[str] = []
    if device == "unknown":
        blockers.append("device type is not specified")
    frequency_devices = {"JPA", "transmon", "CPW_resonator", "SQUID"}
    if device in frequency_devices and target["frequency_ghz"] is None:
        blockers.append("target frequency is not specified")

    jc = supplied.get("jc_ua_per_um2")
    area = supplied.get("junction_area_um2")
    if area is None and supplied.get("junction_width_um") and supplied.get("junction_height_um"):
        area = float(supplied["junction_width_um"]) * float(supplied["junction_height_um"])
        if int(supplied.get("junction_count", 1)) > 1:
            area *= int(supplied["junction_count"])
    ic_a = None
    lj_h = None
    if jc is not None and area is not None:
        ic_a = float(jc) * float(area) * 1e-6
        if ic_a > 0.0:
            lj_h = PHI0_WEBER / (2.0 * math.pi * ic_a)
        else:
            blockers.append("derived critical current is not positive")
    elif device in {"JPA", "SQUID", "transmon", "Josephson_junction"}:
        blockers.append("Jc and junction area or dimensions are required")

    inductance_h = (
        float(supplied["inductance_ph"]) * 1e-12
        if supplied.get("inductance_ph") is not None
        else lj_h
    )
    capacitance_f = (
        float(supplied["capacitance_ff"]) * 1e-15
        if supplied.get("capacitance_ff") is not None
        else None
    )
    if target["frequency_ghz"] and inductance_h and capacitance_f is None:
        omega = 2.0 * math.pi * target["frequency_ghz"] * 1e9
        capacitance_f = 1.0 / (omega * omega * inductance_h)
    elif target["frequency_ghz"] and capacitance_f and inductance_h is None:
        omega = 2.0 * math.pi * target["frequency_ghz"] * 1e9
        inductance_h = 1.0 / (omega * omega * capacitance_f)
    if device in {"JPA", "transmon"} and (
        inductance_h is None or capacitance_f is None
    ):
        blockers.append("circuit synthesis requires both L and C or one value plus target frequency")

    q_external = supplied.get("q_external")
    if q_external is None and target["frequency_ghz"] and target["bandwidth_mhz"]:
        q_external = target["frequency_ghz"] * 1000.0 / target["bandwidth_mhz"]
    if device in {"JPA", "CPW_resonator"} and q_external is None:
        blockers.append("external coupling Q or bandwidth is required")

    cpw = None
    cpw_keys = {
        "center_width_um",
        "gap_um",
        "ground_width_um",
        "epsilon_r",
        "substrate_thickness_um",
    }
    if cpw_keys.intersection(supplied) or device in {"JPA", "CPW_resonator"}:
        missing = sorted(key for key in cpw_keys if supplied.get(key) is None)
        if missing or target["frequency_ghz"] is None:
            blockers.append(f"missing CPW synthesis inputs: {', '.join(missing)}")
        else:
            cpw = synthesize_cpw(
                center_width_um=float(supplied["center_width_um"]),
                gap_um=float(supplied["gap_um"]),
                ground_width_um=float(supplied["ground_width_um"]),
                epsilon_r=float(supplied["epsilon_r"]),
                substrate_thickness_um=float(supplied["substrate_thickness_um"]),
                frequency_ghz=float(target["frequency_ghz"]),
                target_impedance_ohm=float(target["impedance_ohm"]),
                impedance_tolerance_ohm=float(supplied.get("impedance_tolerance_ohm", 2.5)),
                substrate=str(supplied.get("substrate", "unspecified")),
            )
            if cpw["status"] != "ok":
                blockers.append(cpw["reason"])

    pump = {
        "frequency_ghz": supplied.get("pump_frequency_ghz"),
        "power_dbm": supplied.get("pump_power_dbm"),
        "mode": supplied.get("pump_mode"),
    }
    if device == "JPA" and any(value is None for value in pump.values()):
        blockers.append("pump frequency, power, and mode are required for a JPA")
    externally_connected = {
        "JPA",
        "SQUID",
        "transmon",
        "CPW_resonator",
        "Josephson_junction",
        "process_monitor",
    }
    if device in externally_connected and supplied.get("package_clearance_um") is None:
        blockers.append("package clearance is required")
    if device in externally_connected and not supplied.get("wirebond_pads"):
        blockers.append("wirebond or probe pads are required")

    physics = {
        "junction_area_um2": float(area) if area is not None else None,
        "jc_ua_per_um2": float(jc) if jc is not None else None,
        "critical_current_a": ic_a,
        "josephson_inductance_h": lj_h,
        "inductance_required_h": inductance_h,
        "capacitance_required_f": capacitance_f,
        "coupling_q": float(q_external) if q_external is not None else None,
        "pump_condition": pump,
        "cpw": cpw,
    }
    return {
        "schema": "text-to-gds.design-intent.v1",
        "status": "ready" if not blockers else "failed",
        "reason": None if not blockers else blockers[0],
        "prompt": prompt,
        "device": device,
        "target": target,
        "physics": physics,
        "layout_constraints": {
            "die_size_mm": supplied.get("die_size_mm"),
            "package_clearance_um": supplied.get("package_clearance_um"),
            "process": supplied.get("process"),
        },
        "measurement": {
            "rf_ports": supplied.get("rf_ports"),
            "dc_bias": supplied.get("dc_bias"),
            "flux_line": supplied.get("flux_line"),
            "wirebond_pads": supplied.get("wirebond_pads"),
        },
        "blockers": blockers,
        "lineage": {
            "Ic": "Jc * junction_area",
            "Lj": "Phi0/(2*pi*Ic)",
            "resonance": "1/(2*pi*sqrt(L*C))",
            "Q_external": "frequency/bandwidth when bandwidth is specified",
        },
    }


def write_design_intent(intent: dict[str, Any], path: str | Path) -> dict[str, Any]:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(intent, indent=2), encoding="utf-8")
    intent["result_path"] = str(output)
    return intent
