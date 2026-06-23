"""Quarter-wave resonator physical acceptance checks."""

from __future__ import annotations

from typing import Any


def check_resonator(
    sidecar: dict[str, Any],
    extraction: dict[str, Any],
    *,
    length_tolerance_fraction: float = 0.02,
    frequency_tolerance_fraction: float = 0.02,
    q_external_range: tuple[float, float] = (10.0, 1e7),
) -> dict[str, Any]:
    info = sidecar.get("info", {})
    ports = {str(port.get("name", "")).lower() for port in sidecar.get("ports", [])}
    circuit = extraction.get("linear_circuit", {})
    cpw = extraction.get("cpw") or info.get("cpw_physics") or {}
    checks: dict[str, dict[str, Any]] = {}

    checks["open_end"] = {"passed": "resonator_open" in ports, "value": sorted(ports)}
    boundary = str(info.get("boundary_condition", "")).lower()
    layers = info.get("layers", {})
    checks["short_end"] = {
        "passed": "short" in boundary and "short_via" in layers,
        "value": boundary,
    }
    coupling_length = info.get("coupling_length_um")
    coupling_gap = info.get("coupling_gap_um")
    checks["coupling_capacitor"] = {
        "passed": bool(coupling_length and coupling_gap),
        "value": {"length_um": coupling_length, "gap_um": coupling_gap},
    }

    actual_length = info.get("electrical_length_um")
    expected_length = cpw.get("quarter_wave_length_um")
    length_error = None
    if actual_length and expected_length:
        length_error = abs(float(actual_length) - float(expected_length)) / float(expected_length)
    checks["quarter_wave_length"] = {
        "passed": length_error is not None and length_error <= length_tolerance_fraction,
        "relative_error": length_error,
        "tolerance": length_tolerance_fraction,
    }

    target = info.get("target_frequency_ghz")
    extracted_hz = circuit.get("resonance_frequency")
    frequency_error = None
    if target and extracted_hz:
        frequency_error = abs(float(extracted_hz) / 1e9 - float(target)) / float(target)
    checks["mode_frequency"] = {
        "passed": frequency_error is not None and frequency_error <= frequency_tolerance_fraction,
        "relative_error": frequency_error,
        "tolerance": frequency_tolerance_fraction,
    }

    q_external = circuit.get("q_external")
    checks["q_external"] = {
        "passed": q_external is not None and q_external_range[0] <= float(q_external) <= q_external_range[1],
        "value": q_external,
        "range": list(q_external_range),
    }
    failed = [name for name, check in checks.items() if not check["passed"]]
    return {
        "schema": "text-to-gds.resonator-check.v1",
        "status": "PASS" if not failed else "FAIL",
        "passed": not failed,
        "checks": checks,
        "failed_checks": failed,
    }
