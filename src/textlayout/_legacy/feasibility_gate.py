"""Pre-layout feasibility gate.

Before any GDS is generated, answer "Can this exist?". This wires the device
physics template (validity ranges + applicable constraints) together with the
physics constraint engine (Bode-Fano, Manley-Rowe, Kerr, quantum noise, ...) and
returns a single ACCEPT/REJECT decision with the reasons. Infeasible requests
are rejected here so no compute is spent generating an impossible device.
"""

from __future__ import annotations

from typing import Any

from textlayout._legacy.physics_constraints import check_all_constraints
from textlayout._legacy.physics_templates import load_template


def _range_violations(targets: dict[str, Any], validity: dict[str, Any]) -> list[dict[str, Any]]:
    violations = []
    for key, bounds in validity.items():
        if key not in targets or not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            continue
        low, high = float(bounds[0]), float(bounds[1])
        try:
            value = float(targets[key])
        except (TypeError, ValueError):
            continue
        if value < low or value > high:
            violations.append(
                {
                    "parameter": key,
                    "value": value,
                    "valid_range": [low, high],
                    "message": f"{key}={value} outside template range [{low}, {high}]",
                }
            )
    return violations


def check_design_feasibility(
    device: str,
    targets: dict[str, Any],
    *,
    device_id: str = "",
) -> dict[str, Any]:
    """Decide whether a requested device specification can physically exist.

    ``targets`` may include gain_db, bandwidth_mhz, frequency_ghz,
    quality_factor, anharmonicity_ghz, pump_frequency_ghz, critical_current_ua,
    etc. (the same keys the physics constraint engine understands).
    """
    template = None
    template_error = None
    try:
        template = load_template(device)
    except KeyError as exc:
        template_error = str(exc)

    validity = template.get("validity", {}) if template else {}
    range_violations = _range_violations(targets, validity)

    constraint_report = check_all_constraints(targets, device_id=device_id).to_dict()
    constraint_blockers = [
        r for r in constraint_report["results"] if not r["passed"] and r["severity"] == "error"
    ]

    blockers: list[str] = []
    blockers += [v["message"] for v in range_violations]
    blockers += [f"{r['name']}: {r['message']}" for r in constraint_blockers]

    accepted = not blockers
    return {
        "schema": "text-to-gds.feasibility-gate.v1",
        "device": device,
        "device_id": device_id,
        "template": template["template_name"] if template else None,
        "template_warning": template_error,
        "accepted": accepted,
        "verdict": "feasible" if accepted else "infeasible",
        "blockers": blockers,
        "range_violations": range_violations,
        "constraint_report": constraint_report,
        "recommendation": (
            "Specification is physically feasible; proceed to layout generation."
            if accepted
            else "Reject before layout: adjust targets to clear the blockers above."
        ),
    }
