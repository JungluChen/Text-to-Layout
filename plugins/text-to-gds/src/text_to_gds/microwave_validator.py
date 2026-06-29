from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field


class MicrowaveReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema: str = "text-to-gds.microwave-report.v1"
    status: str
    source: str
    active_mode: bool
    reciprocity: dict[str, Any]
    energy_conservation: dict[str, Any]
    stability: dict[str, Any]
    resonance: dict[str, Any]
    errors: list[str] = Field(default_factory=list)


def write_microwave_report(
    touchstone_path: str | Path,
    report_path: str | Path,
    *,
    active_mode: bool = False,
    reciprocity_tolerance: float = 1e-3,
    energy_tolerance: float = 1e-6,
) -> dict[str, Any]:
    """Validate S-parameter physics and extract resonance features.

    Passive mode enforces reciprocity and power conservation. Active mode still
    reports those metrics but allows gain while checking finite/stable data.
    """
    source = Path(touchstone_path)
    report = Path(report_path)
    errors: list[str] = []

    if not source.is_file():
        payload = MicrowaveReport(
            status="failed",
            source=str(source),
            active_mode=active_mode,
            reciprocity={"passed": False, "max_error": None},
            energy_conservation={"passed": False, "max_power_sum": None},
            stability={"passed": False, "max_gain_db": None},
            resonance={},
            errors=[f"Touchstone file not found: {source}"],
        ).model_dump(mode="json")
        _write(report, payload)
        return payload

    freqs_hz, matrices = _load_touchstone(source)
    if len(freqs_hz) < 2 or len(matrices) != len(freqs_hz):
        errors.append("Touchstone file has insufficient parseable S-parameter data")

    max_recip = 0.0
    max_power_sum = 0.0
    max_gain_db = -math.inf
    s21_db: list[float] = []
    for matrix in matrices:
        if not np.all(np.isfinite(matrix)):
            errors.append("S-matrix contains non-finite values")
            continue
        max_recip = max(max_recip, float(abs(matrix[1, 0] - matrix[0, 1])))
        max_power_sum = max(
            max_power_sum,
            float(abs(matrix[0, 0]) ** 2 + abs(matrix[1, 0]) ** 2),
            float(abs(matrix[1, 1]) ** 2 + abs(matrix[0, 1]) ** 2),
        )
        gain_db = 20.0 * math.log10(max(abs(matrix[1, 0]), 1e-300))
        s21_db.append(gain_db)
        max_gain_db = max(max_gain_db, gain_db)

    reciprocity_pass = max_recip <= reciprocity_tolerance
    energy_pass = active_mode or max_power_sum <= 1.0 + energy_tolerance
    stability_pass = bool(s21_db) and all(math.isfinite(v) for v in s21_db)
    if not active_mode and max_gain_db > 1e-6:
        stability_pass = False
        errors.append("passive device shows nonphysical positive S21 gain")
    if not reciprocity_pass and not active_mode:
        errors.append("passive device violates reciprocity")
    if not energy_pass:
        errors.append("passive device violates energy conservation")

    resonance = _extract_resonance(freqs_hz, s21_db)
    status = "ok" if not errors and reciprocity_pass and energy_pass and stability_pass else "failed"

    payload = MicrowaveReport(
        status=status,
        source=str(source),
        active_mode=active_mode,
        reciprocity={"passed": reciprocity_pass, "max_error": max_recip, "tolerance": reciprocity_tolerance},
        energy_conservation={"passed": energy_pass, "max_power_sum": max_power_sum, "tolerance": energy_tolerance},
        stability={"passed": stability_pass, "max_gain_db": None if max_gain_db == -math.inf else max_gain_db},
        resonance=resonance,
        errors=errors,
    ).model_dump(mode="json")
    _write(report, payload)
    return payload


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["report_path"] = str(path)


def _load_touchstone(path: Path) -> tuple[list[float], list[np.ndarray]]:
    freqs: list[float] = []
    matrices: list[np.ndarray] = []
    unit_scale = 1.0
    fmt = "RI"
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("!"):
            continue
        if line.startswith("#"):
            tokens = line.upper().split()
            if len(tokens) > 1:
                unit_scale = {"HZ": 1.0, "KHZ": 1e3, "MHZ": 1e6, "GHZ": 1e9}.get(tokens[1], 1.0)
            if "DB" in tokens:
                fmt = "DB"
            elif "MA" in tokens:
                fmt = "MA"
            else:
                fmt = "RI"
            continue
        parts = line.split()
        if len(parts) < 9:
            continue
        try:
            freq = float(parts[0]) * unit_scale
            values = [float(v) for v in parts[1:9]]
        except ValueError:
            continue
        s11 = _pair(values[0], values[1], fmt)
        s21 = _pair(values[2], values[3], fmt)
        s12 = _pair(values[4], values[5], fmt)
        s22 = _pair(values[6], values[7], fmt)
        freqs.append(freq)
        matrices.append(np.array([[s11, s12], [s21, s22]], dtype=complex))
    return freqs, matrices


def _pair(a: float, b: float, fmt: str) -> complex:
    if fmt == "DB":
        mag = 10.0 ** (a / 20.0)
        angle = math.radians(b)
        return complex(mag * math.cos(angle), mag * math.sin(angle))
    if fmt == "MA":
        angle = math.radians(b)
        return complex(a * math.cos(angle), a * math.sin(angle))
    return complex(a, b)


def _extract_resonance(freqs_hz: list[float], s21_db: list[float]) -> dict[str, Any]:
    if len(freqs_hz) < 3 or len(s21_db) != len(freqs_hz):
        return {"status": "not_available", "reason": "insufficient S21 data"}
    peak_index = max(range(len(s21_db)), key=s21_db.__getitem__)
    notch_index = min(range(len(s21_db)), key=s21_db.__getitem__)
    baseline = (s21_db[0] + s21_db[-1]) / 2.0
    peak_prominence = s21_db[peak_index] - baseline
    notch_depth = baseline - s21_db[notch_index]
    index = peak_index if peak_prominence >= notch_depth else notch_index
    kind = "peak" if index == peak_index else "notch"
    level = s21_db[index] - 3.0 if kind == "peak" else s21_db[index] + 3.0
    if kind == "peak":
        selected = [i for i, value in enumerate(s21_db) if value >= level]
    else:
        selected = [i for i, value in enumerate(s21_db) if value <= level]
    bandwidth_hz = None
    q_loaded = None
    if selected:
        bandwidth_hz = freqs_hz[max(selected)] - freqs_hz[min(selected)]
        if bandwidth_hz > 0.0:
            q_loaded = freqs_hz[index] / bandwidth_hz
    return {
        "status": "ok",
        "kind": kind,
        "f0_hz": freqs_hz[index],
        "f0_ghz": freqs_hz[index] / 1e9,
        "bandwidth_hz": bandwidth_hz,
        "bandwidth_mhz": None if bandwidth_hz is None else bandwidth_hz / 1e6,
        "q_loaded": q_loaded,
    }
