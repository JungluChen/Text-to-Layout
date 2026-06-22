"""Physics reviewer: topology sanity, impedance realism, frequency match."""

from __future__ import annotations

from typing import Any

from text_to_gds.review.base import device_text, finding, port_names, review_result

_AGENT = "physics"


def _has_ground(evidence: dict[str, Any]) -> bool:
    sidecar = evidence.get("sidecar") or {}
    info = sidecar.get("info") or {}
    if info.get("has_ground_plane") or info.get("ground_plane"):
        return True
    blob = " ".join(port_names(evidence) + [str(label) for label in sidecar.get("labels") or []]).lower()
    if "ground" in blob or "gnd" in blob:
        return True
    for layer in sidecar.get("layers") or []:
        gds_layer = layer.get("layer") if isinstance(layer, dict) else layer
        if list(gds_layer or []) == [10, 0]:
            return True
    return False


def review_physics(evidence: dict[str, Any]) -> dict[str, Any]:
    sidecar = evidence.get("sidecar") or {}
    sim = evidence.get("simulation") or {}
    info = sidecar.get("info") or {}
    text = device_text(evidence)
    ports = port_names(evidence)
    findings: list[dict[str, Any]] = []

    if not ports:
        findings.append(
            finding(_AGENT, "error", "No ports defined; topology cannot be extracted.",
                    "Add input/output ports to the PCell.")
        )

    if any(k in text for k in ("cpw", "coplanar", "resonator")) and not _has_ground(evidence):
        findings.append(
            finding(_AGENT, "error",
                    "CPW/resonator has no ground plane or signal-ground gap; Z0 is undefined.",
                    "Regenerate the CPW with ground planes and a defined gap.")
        )

    impedance = info.get("impedance_ohm", info.get("z0_ohm"))
    if impedance is not None:
        try:
            z = float(impedance)
            if not 20.0 <= z <= 120.0:
                findings.append(
                    finding(_AGENT, "error", f"Impedance {z:.1f} ohm is unphysical for this geometry.",
                            "Target a 20-120 ohm characteristic impedance.")
                )
        except (TypeError, ValueError):
            pass

    target = info.get("target_frequency_ghz")
    performance = sim.get("physical_performance") or {}
    got = performance.get("center_frequency_ghz") or sim.get("center_frequency_ghz")
    if target and got:
        rel = abs(float(got) - float(target)) / float(target)
        if rel > 0.2:
            findings.append(
                finding(_AGENT, "warning",
                        f"Simulated f0 {float(got):.3f} GHz is {rel * 100:.0f}% off target {float(target):.3f} GHz.",
                        "Tune resonator length or shunt capacitance.")
            )

    return review_result(_AGENT, findings)
