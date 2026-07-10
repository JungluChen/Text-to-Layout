"""Simulation-to-measurement comparison and process correction suggestions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textlayout._legacy.fitting import measurement_from_fit, write_measurement_fit


def _load_json(path_or_payload: dict[str, Any] | str | Path | None) -> dict[str, Any]:
    if path_or_payload is None:
        return {}
    if isinstance(path_or_payload, dict):
        return path_or_payload
    return json.loads(Path(path_or_payload).read_text(encoding="utf-8"))


def _predicted_measurement(simulation: dict[str, Any]) -> dict[str, Any]:
    if "measurement_prediction" in simulation:
        return dict(simulation["measurement_prediction"])
    if "metrics" in simulation:
        metrics = simulation["metrics"]
        return {
            "center_frequency_ghz": metrics.get("center_frequency_ghz"),
            "peak_gain_db": metrics.get("peak_gain_db"),
            "bandwidth_3db_mhz": metrics.get("bandwidth_3db_mhz") or metrics.get("bandwidth_mhz"),
        }
    sweep = simulation.get("sweep") if isinstance(simulation.get("sweep"), dict) else {}
    return {
        "center_frequency_ghz": sweep.get("center_frequency_ghz"),
        "peak_gain_db": simulation.get("best_peak_gain_db") or sweep.get("best_peak_gain_db"),
        "bandwidth_3db_mhz": simulation.get("bandwidth_3db_mhz"),
    }


def _corrections(sim: dict[str, Any], meas: dict[str, Any]) -> dict[str, Any]:
    corrections: dict[str, Any] = {}
    sf = sim.get("center_frequency_ghz")
    mf = meas.get("center_frequency_ghz")
    if sf and mf:
        ratio = float(sf) / float(mf)
        corrections["effective_epsilon_scale"] = ratio * ratio
        corrections["frequency_error_pct"] = (float(mf) - float(sf)) / float(sf) * 100.0
    sg = sim.get("peak_gain_db")
    mg = meas.get("peak_gain_db")
    if sg is not None and mg is not None:
        corrections["gain_error_db"] = float(mg) - float(sg)
    sbw = sim.get("bandwidth_3db_mhz")
    mbw = meas.get("bandwidth_3db_mhz")
    if sbw and mbw:
        corrections["coupling_q_scale"] = float(sbw) / float(mbw)
    if sim.get("critical_current_ua") and meas.get("critical_current_ua"):
        corrections["junction_jc_scale"] = float(meas["critical_current_ua"]) / float(sim["critical_current_ua"])
    if "effective_epsilon_scale" in corrections:
        corrections["kinetic_inductance_scale"] = max(corrections["effective_epsilon_scale"] - 1.0, 0.0)
    return corrections


def compare_measurement_to_simulation(
    measurement_path: str | Path,
    simulation: dict[str, Any] | str | Path | None,
    *,
    report_path: str | Path,
    plot_path: str | Path | None = None,
    fit_kind: str = "auto",
) -> dict[str, Any]:
    """Fit measurement trace, compare to simulation, and output process corrections."""
    report = Path(report_path)
    plot = Path(plot_path) if plot_path is not None else report.with_suffix(".png")
    fit_report = write_measurement_fit(
        measurement_path,
        report_path=report.with_suffix(".fit.json"),
        plot_path=plot,
        fit_kind=fit_kind,
    )
    measured = measurement_from_fit(fit_report["fit"])
    predicted = _predicted_measurement(_load_json(simulation))
    corrections = _corrections(predicted, measured)
    result = {
        "schema": "text-to-gds.measurement-comparison.v1",
        "status": "ok",
        "measurement_source": str(measurement_path),
        "fit_report_path": fit_report["report_path"],
        "simulation_prediction": predicted,
        "measurement": measured,
        "process_correction": corrections,
        "correction_targets": ["effective epsilon", "junction Jc", "kinetic inductance"],
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["report_path"] = str(report)
    return result

