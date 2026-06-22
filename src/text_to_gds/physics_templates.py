"""Device physics templates.

Each device family (CPW, Resonator, JPA, JTWPA, SFQ, Transmon) has a YAML
template under ``device_templates/`` declaring the features a valid layout
*must have*, the governing equations, the parameter validity ranges, and which
physics constraint checks apply. The feasibility gate and the (future) physics
reviewer use these as the contract for "is this the right kind of device".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_TEMPLATE_DIR = Path(__file__).resolve().parent / "device_templates"


def list_templates() -> list[str]:
    """Return the available device template names (lower-case stems)."""
    return sorted(path.stem for path in _TEMPLATE_DIR.glob("*.yaml"))


def _resolve_path(device: str) -> Path | None:
    key = str(device or "").strip().lower()
    if not key:
        return None
    exact = _TEMPLATE_DIR / f"{key}.yaml"
    if exact.exists():
        return exact
    # Substring match: "cpw_resonator" -> resonator/cpw, "transmon qubit" -> transmon.
    for path in sorted(_TEMPLATE_DIR.glob("*.yaml")):
        if path.stem in key:
            return path
    return None


def load_template(device: str) -> dict[str, Any]:
    """Load a device template by name. Raises KeyError if there is no match."""
    path = _resolve_path(device)
    if path is None:
        raise KeyError(
            f"No physics template for device '{device}'. Available: {', '.join(list_templates())}"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["template_name"] = path.stem
    return data


def _port_names(sidecar: dict[str, Any]) -> set[str]:
    ports = sidecar.get("ports", []) if isinstance(sidecar, dict) else []
    names = set()
    for port in ports:
        if isinstance(port, dict) and port.get("name"):
            names.add(str(port["name"]).lower())
    return names


def _device_text(sidecar: dict[str, Any]) -> str:
    info = sidecar.get("info", {}) if isinstance(sidecar.get("info"), dict) else {}
    return f"{sidecar.get('pcell', '')} {info.get('device_type', '')}".lower()


def _feature_status(feature: str, sidecar: dict[str, Any]) -> str:
    """Best-effort detection of a required feature in a sidecar.

    Returns 'satisfied' when reliably detected, 'missing' when reliably absent,
    or 'review_required' when the sidecar cannot confirm it either way.
    """
    ports = _port_names(sidecar)
    text = _device_text(sidecar)
    n_ports = len(ports)

    if feature in {"input_port", "output_port", "drive_port", "readout_port"}:
        return "satisfied" if n_ports >= 1 else "missing"
    if feature in {"junction", "junction_array"}:
        return "satisfied" if any(k in text for k in ("jj", "junction", "squid")) else "review_required"
    if feature in {"ground_plane", "ground_planes"}:
        return "satisfied" if "ground" in text or "ground" in " ".join(ports) else "review_required"
    if feature == "signal_conductor":
        return "satisfied" if n_ports >= 1 else "review_required"
    # Geometric/coupling features are not reliably inferable from the sidecar.
    return "review_required"


def validate_sidecar(sidecar: dict[str, Any], device: str) -> dict[str, Any]:
    """Check a sidecar against a device template's must-have feature list."""
    template = load_template(device)
    must_have = template.get("must_have", [])
    features = [{"feature": f, "status": _feature_status(f, sidecar)} for f in must_have]
    missing = [f["feature"] for f in features if f["status"] == "missing"]
    review = [f["feature"] for f in features if f["status"] == "review_required"]
    satisfied = [f["feature"] for f in features if f["status"] == "satisfied"]
    return {
        "schema": "text-to-gds.template-validation.v1",
        "device": template["device"],
        "template_name": template["template_name"],
        "features": features,
        "satisfied": satisfied,
        "missing": missing,
        "review_required": review,
        "passed": not missing,
        "model_validity": (
            "Feature detection is sidecar-based and best-effort. 'review_required' "
            "items need a layout/EM check; they are not asserted present or absent."
        ),
    }
