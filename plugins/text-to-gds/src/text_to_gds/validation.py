from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _exists(path_value: str | None) -> bool:
    return bool(path_value) and Path(str(path_value)).exists()


def _item(name: str, passed: bool, evidence: str, *, severity: str = "required") -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else "warning",
        "severity": severity,
        "evidence": evidence,
    }


def _load_json(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    candidate = Path(path)
    if not candidate.exists():
        return {}
    try:
        value = json.loads(candidate.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _port_names(sidecar: dict[str, Any]) -> set[str]:
    return {
        str(port.get("name"))
        for port in sidecar.get("ports", [])
        if isinstance(port, dict) and port.get("name")
    }


def _simulation_physical(simulation: dict[str, Any]) -> dict[str, Any]:
    physical = simulation.get("physical_performance")
    return physical if isinstance(physical, dict) else {}


def _has_any_key(payload: dict[str, Any], keys: tuple[str, ...]) -> bool:
    if any(key in payload for key in keys):
        return True
    return any(
        isinstance(value, dict) and any(key in value for key in keys)
        for value in payload.values()
    )


# Ordered technology-readiness stages. The TRL is gated: it advances only while
# each leading stage meets the evidence threshold, so a downstream stage cannot
# inflate the level past an unmet upstream gate.
_TRL_STAGES: tuple[tuple[str, str], ...] = (
    ("layout_fabrication", "Layout"),
    ("drc", "DRC"),
    ("extraction", "Extraction"),
    ("simulation_characterization", "Circuit simulation"),
    ("electromagnetic", "EM extraction"),
    ("measurement", "Measurement"),
)
_TRL_PASS_THRESHOLD = 0.8
_TRL_DESCRIPTIONS = {
    1: "Concept only",
    2: "Layout generated",
    3: "Design-rule clean",
    4: "Extraction complete",
    5: "Circuit simulation evidence",
    6: "EM-extraction validated",
    7: "Measurement-correlated design",
}


def _readiness(sections: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    stages = []
    trl = 1
    gate_open = True
    for key, label in _TRL_STAGES:
        items = sections.get(key, [])
        total = len(items)
        passed = sum(1 for item in items if item["status"] == "pass")
        percent = round(100.0 * passed / total, 1) if total else 0.0
        meets = total > 0 and (passed / total) >= _TRL_PASS_THRESHOLD
        if gate_open and meets:
            trl += 1
        else:
            gate_open = False
        stages.append(
            {
                "stage": label,
                "section": key,
                "passed": passed,
                "total": total,
                "percent": percent,
                "meets_threshold": meets,
            }
        )
    trl = min(trl, 9)
    overall_percent = round(sum(stage["percent"] for stage in stages) / len(stages), 1)
    return {
        "technology_readiness_level": trl,
        "trl_scale": 9,
        "trl_label": _TRL_DESCRIPTIONS.get(trl, "Qualified / flight (beyond toolkit scope)"),
        "overall_percent": overall_percent,
        "threshold_percent": int(_TRL_PASS_THRESHOLD * 100),
        "stages": stages,
        "model_validity": (
            "TRL is gated on contiguous stage evidence in this toolkit (max 7); "
            "TRL 8-9 require system qualification beyond layout/EM/measurement artifacts."
        ),
    }


def build_validation_report(
    *,
    gds_path: str | Path | None = None,
    sidecar_path: str | Path | None = None,
    drc_path: str | Path | None = None,
    extraction_path: str | Path | None = None,
    simulation_path: str | Path | None = None,
    cad_path: str | Path | None = None,
    em_path: str | Path | None = None,
    measurement_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build a roadmap-style academic/industrial validation checklist."""
    sidecar = _load_json(sidecar_path)
    drc = _load_json(drc_path)
    extraction = _load_json(extraction_path)
    simulation = _load_json(simulation_path)
    cad = _load_json(cad_path)
    em = _load_json(em_path)
    measurement = _load_json(measurement_path)
    info = sidecar.get("info", {}) if isinstance(sidecar.get("info"), dict) else {}
    process_stack = sidecar.get("process_stack")
    physical = _simulation_physical(simulation)
    ports = _port_names(sidecar)
    flux_tuning = physical.get("flux_tuning") if isinstance(physical.get("flux_tuning"), dict) else None
    cad_outputs = cad.get("outputs") if isinstance(cad.get("outputs"), dict) else {}

    layout_items = [
        _item("GDS successfully generated", _exists(str(gds_path) if gds_path else None), str(gds_path)),
        _item("Layer mapping verified with process stack", isinstance(process_stack, dict), "sidecar.process_stack"),
        _item("Ports correctly assigned", bool(ports), ", ".join(sorted(ports)) or "missing"),
        _item(
            "Junction overlap area extracted",
            "junction_area_um2" in info,
            f"junction_area_um2={info.get('junction_area_um2')}",
        ),
        _item(
            "SQUID loop geometry verified",
            "squid_loop_area_um2" in info,
            f"squid_loop_area_um2={info.get('squid_loop_area_um2')}",
        ),
        _item(
            "Flux line coupling geometry checked",
            {"flux_in", "flux_out"} <= ports or "flux_line_length_um" in info,
            "flux ports present" if {"flux_in", "flux_out"} <= ports else "flux metadata missing",
        ),
        _item("CAD SVG generated", _exists(cad_outputs.get("layout_svg")), str(cad_outputs.get("layout_svg"))),
        _item("CAD DXF generated", _exists(cad_outputs.get("layout_dxf")), str(cad_outputs.get("layout_dxf"))),
        _item("3D stack solid generated", _exists(cad_outputs.get("stack_stl")), str(cad_outputs.get("stack_stl"))),
    ]

    drc_items = [
        _item("DRC report exists", bool(drc), str(drc_path)),
        _item("DRC status passed", drc.get("status") == "passed", str(drc.get("status"))),
        _item(
            "Minimum width/spacing checks ran",
            bool(drc.get("checked_shapes") or drc.get("checked_spacing_pairs")),
            f"checked_shapes={drc.get('checked_shapes')}",
        ),
    ]

    extraction_items = [
        _item("Extraction report exists", bool(extraction), str(extraction_path)),
        _item(
            "Critical current extracted",
            simulation.get("critical_current_ua") is not None,
            f"Ic={simulation.get('critical_current_ua')} uA",
        ),
        _item(
            "Josephson inductance extracted",
            simulation.get("josephson_inductance_ph") is not None,
            f"Lj={simulation.get('josephson_inductance_ph')} pH",
        ),
        _item(
            "Resonator frequency estimated",
            physical.get("center_frequency_ghz") is not None
            or (
                isinstance(flux_tuning, dict)
                and flux_tuning.get("operating_point", {}).get("resonant_frequency_ghz") is not None
            ),
            f"center_frequency_ghz={physical.get('center_frequency_ghz')}",
        ),
        _item(
            "Flux mutual inductance or coil period recorded",
            isinstance(flux_tuning, dict) and flux_tuning.get("flux_period_current_ma") is not None,
            "flux_period_current_ma="
            f"{flux_tuning.get('flux_period_current_ma') if isinstance(flux_tuning, dict) else None}",
            severity="advanced",
        ),
    ]

    simulation_items = [
        _item("Simulation report exists", bool(simulation), str(simulation_path)),
        _item(
            "Flux tuning range simulated",
            isinstance(flux_tuning, dict) and bool(flux_tuning.get("sweep")),
            "flux_tuning.sweep",
        ),
        _item(
            "Gain versus frequency available",
            "adapter_result" in simulation
            and "s_parameters_db" in simulation.get("adapter_result", {}).get("result", {}),
            "JosephsonCircuits S-parameter adapter result",
            severity="advanced",
        ),
        _item(
            "Noise temperature estimated",
            physical.get("quantum_limited_noise_temperature_k") is not None,
            f"Tnoise={physical.get('quantum_limited_noise_temperature_k')} K",
        ),
        _item(
            "Dynamic range estimated",
            physical.get("estimated_input_1db_compression_dbm") is not None,
            f"P1dB={physical.get('estimated_input_1db_compression_dbm')} dBm",
        ),
    ]

    em_items = [
        _item("EM extraction report exists", bool(em), str(em_path), severity="advanced"),
        _item(
            "EM solved S-parameters or capacitance",
            _has_any_key(
                em,
                (
                    "s_parameters",
                    "s_parameters_db",
                    "capacitance_matrix",
                    "eigenmodes",
                    "touchstone_s2p",
                ),
            )
            or em.get("status") in {"solved", "executed", "executed_with_warnings"},
            f"status={em.get('status')}",
            severity="advanced",
        ),
    ]

    measurement_metrics = (
        measurement.get("fit") if isinstance(measurement.get("fit"), dict) else measurement
    )
    measurement_items = [
        _item(
            "Measurement/fit report exists",
            bool(measurement),
            str(measurement_path),
            severity="advanced",
        ),
        _item(
            "Measured device metric available",
            _has_any_key(
                measurement_metrics,
                ("center_frequency_ghz", "f0_ghz", "peak_gain_db", "internal_q", "noise_temperature_k"),
            ),
            "fitted device metrics present",
            severity="advanced",
        ),
    ]

    sections = {
        "layout_fabrication": layout_items,
        "drc": drc_items,
        "extraction": extraction_items,
        "simulation_characterization": simulation_items,
        "electromagnetic": em_items,
        "measurement": measurement_items,
    }
    all_items = [item for items in sections.values() for item in items]
    required = [item for item in all_items if item["severity"] == "required"]
    passed_required = [item for item in required if item["status"] == "pass"]
    return {
        "schema": "text-to-gds.validation-roadmap.v0",
        "status": "pass" if len(passed_required) == len(required) else "warning",
        "summary": {
            "required_passed": len(passed_required),
            "required_total": len(required),
            "advanced_passed": len(
                [item for item in all_items if item["severity"] == "advanced" and item["status"] == "pass"]
            ),
            "advanced_total": len([item for item in all_items if item["severity"] == "advanced"]),
        },
        "readiness": _readiness(sections),
        "sections": sections,
        "model_validity": (
            "Roadmap checklist is evidence bookkeeping. It does not replace foundry DRC, EM "
            "extraction, measured S-parameters, or publication-grade device validation."
        ),
    }
