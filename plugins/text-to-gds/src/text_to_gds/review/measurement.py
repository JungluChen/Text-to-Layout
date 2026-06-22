"""Measurement reviewer: can this device actually be measured?"""

from __future__ import annotations

from typing import Any

from text_to_gds.review.base import device_text, finding, port_names, review_result

_AGENT = "measurement"


def review_measurement(evidence: dict[str, Any]) -> dict[str, Any]:
    text = device_text(evidence)
    ports = port_names(evidence)
    findings: list[dict[str, Any]] = []

    if len(ports) < 2:
        findings.append(
            finding(_AGENT, "error", "No measurable I/O ports; device cannot be probed.",
                    "Add probe/wirebond pads for input and output.")
        )

    if any(k in text for k in ("jpa", "squid", "twpa", "paramp")):
        required = [
            ("input", ("in", "rf_in", "signal")),
            ("output/readout", ("out", "rf_out", "readout")),
            ("pump/flux bias", ("pump", "flux", "bias", "coil")),
        ]
    elif any(k in text for k in ("transmon", "qubit")):
        required = [
            ("drive", ("drive", "xy")),
            ("readout", ("readout", "ro", "out")),
        ]
    else:
        required = []

    for label, keys in required:
        if not any(any(key in name for key in keys) for name in ports):
            findings.append(
                finding(_AGENT, "warning", f"No {label} interface detected in the ports.",
                        f"Add a {label} pad/line so the device can be characterised.")
            )

    return review_result(_AGENT, findings)
