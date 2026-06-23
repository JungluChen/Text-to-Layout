from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# New validation modules (Phases 2-6)
# ---------------------------------------------------------------------------

from text_to_gds.validation.agreement import (
    validate_solver_agreement,
    validate_cpw_agreement,
    validate_capacitance_agreement,
    validate_frequency_agreement,
    full_multi_source_report,
)
from text_to_gds.validation.touchstone import (
    validate_touchstone,
    parse_touchstone_s2p,
    check_reciprocity,
    check_passivity,
    check_energy_conservation,
)

# ---------------------------------------------------------------------------
# Legacy re-exports from the flat validation.py module
# (server.py imports these; they coexist with the new modules above)
# ---------------------------------------------------------------------------


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
    1: "Concept only", 2: "Layout generated", 3: "Design-rule clean",
    4: "Extraction complete", 5: "Circuit simulation evidence",
    6: "EM-extraction validated", 7: "Measurement-correlated design",
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
        stages.append({
            "stage": label, "section": key, "passed": passed,
            "total": total, "percent": percent, "meets_threshold": meets,
        })
    trl = min(trl, 9)
    overall_percent = round(sum(s["percent"] for s in stages) / len(stages), 1)
    return {
        "technology_readiness_level": trl, "trl_scale": 9,
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
    # Import the rest of the implementation from the flat validation.py
    import importlib.util
    import os
    flat = os.path.join(os.path.dirname(os.path.dirname(__file__)), "validation.py")
    if os.path.isfile(flat):
        spec = importlib.util.spec_from_file_location("_validation_flat", flat)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.build_validation_report(
            gds_path=gds_path,
            sidecar_path=sidecar_path,
            drc_path=drc_path,
            extraction_path=extraction_path,
            simulation_path=simulation_path,
            cad_path=cad_path,
            em_path=em_path,
            measurement_path=measurement_path,
        )
    return {
        "schema": "text-to-gds.validation.v0",
        "error": "validation.py flat module not found",
    }


__all__ = [
    "validate_solver_agreement",
    "validate_cpw_agreement",
    "validate_capacitance_agreement",
    "validate_frequency_agreement",
    "full_multi_source_report",
    "validate_touchstone",
    "parse_touchstone_s2p",
    "check_reciprocity",
    "check_passivity",
    "check_energy_conservation",
    "build_validation_report",
]
