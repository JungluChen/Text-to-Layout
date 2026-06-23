from __future__ import annotations

import csv
import json
import math
from importlib.util import find_spec
from pathlib import Path
from typing import Any


def _adapter_payload(simulation: dict[str, Any]) -> dict[str, Any]:
    adapter_result = simulation.get("adapter_result")
    if not isinstance(adapter_result, dict):
        return {}
    result = adapter_result.get("result")
    return result if isinstance(result, dict) else {}


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _finite_list(values: Any) -> list[float]:
    if not isinstance(values, list):
        return []
    result = []
    for value in values:
        number = _finite_float(value)
        if number is not None:
            result.append(number)
    return result


def _center_from_physical(physical: dict[str, Any]) -> float:
    flux_tuning = physical.get("flux_tuning")
    if isinstance(flux_tuning, dict):
        operating = flux_tuning.get("operating_point")
        if isinstance(operating, dict):
            tuned_frequency = _finite_float(operating.get("resonant_frequency_ghz"))
            if tuned_frequency is not None and tuned_frequency > 0.0:
                return tuned_frequency
    center = _finite_float(physical.get("center_frequency_ghz"))
    return center if center is not None and center > 0.0 else 5.0


def _network_from_simulation(
    simulation: dict[str, Any],
) -> tuple[list[float], dict[str, list[float]], str] | None:
    """Extract real S-parameter data from a simulation result dict.

    Returns None when no real solver data is present — the caller must then
    return status='skipped', never synthesise fake curves.
    """
    payload = _adapter_payload(simulation)
    frequencies = _finite_list(payload.get("frequencies_ghz"))
    s_parameters = payload.get("s_parameters_db")
    if frequencies and isinstance(s_parameters, dict):
        extracted = {
            key: _finite_list(s_parameters.get(key))
            for key in ("s11_db", "s21_db", "s12_db", "s22_db")
        }
        if all(len(values) == len(frequencies) for values in extracted.values()):
            return frequencies, extracted, "josephsoncircuits_adapter"

    reflection = _finite_list(payload.get("reflection_gain_db"))
    if frequencies and len(reflection) == len(frequencies):
        return (
            frequencies,
            {
                "s11_db": reflection,
                "s21_db": [-120.0 for _ in frequencies],
                "s12_db": [-120.0 for _ in frequencies],
                "s22_db": reflection,
            },
            "single_port_reflection_adapter",
        )

    return None


def _read_touchstone_data(
    path: Path,
) -> tuple[list[float], dict[str, list[float]]]:
    """Parse a 2-port Touchstone file and return (frequencies_ghz, s_parameters_db).

    Handles only the dB/angle format (#GHZ S DB R ...) that this module writes.
    Falls back to empty lists if the file cannot be parsed — the caller will
    produce an incomplete result, but never fake data.
    """
    freqs: list[float] = []
    s11, s21, s12, s22 = [], [], [], []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("!") or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) >= 9:
                try:
                    freqs.append(float(parts[0]))
                    s11.append(float(parts[1]))
                    s21.append(float(parts[3]))
                    s12.append(float(parts[5]))
                    s22.append(float(parts[7]))
                except (ValueError, IndexError):
                    continue
    except OSError:
        pass
    return freqs, {"s11_db": s11, "s21_db": s21, "s12_db": s12, "s22_db": s22}


def _touchstone_text(
    frequencies_ghz: list[float],
    s_parameters_db: dict[str, list[float]],
    *,
    reference_ohm: float,
) -> str:
    lines = [
        "! Text-to-GDS generated S-parameter export",
        "! Format: magnitude in dB, zero phase when source data has no phase.",
        f"# GHZ S DB R {reference_ohm:.12g}",
    ]
    for index, frequency in enumerate(frequencies_ghz):
        row = [
            frequency,
            s_parameters_db["s11_db"][index],
            0.0,
            s_parameters_db["s21_db"][index],
            0.0,
            s_parameters_db["s12_db"][index],
            0.0,
            s_parameters_db["s22_db"][index],
            0.0,
        ]
        lines.append(" ".join(f"{value:.12g}" for value in row))
    return "\n".join(lines) + "\n"


def _bandwidth_3db_mhz(frequencies: list[float], s21_db: list[float]) -> float | None:
    if len(frequencies) < 2 or len(frequencies) != len(s21_db):
        return None
    peak = max(s21_db)
    peak_index = s21_db.index(peak)
    threshold = peak - 3.0
    left = peak_index
    right = peak_index
    while left > 0 and s21_db[left - 1] >= threshold:
        left -= 1
    while right < len(s21_db) - 1 and s21_db[right + 1] >= threshold:
        right += 1
    return max(frequencies[right] - frequencies[left], 0.0) * 1000.0


def _write_csv(
    csv_path: Path,
    frequencies: list[float],
    s_parameters: dict[str, list[float]],
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["frequency_ghz", "s11_db", "s21_db", "s12_db", "s22_db"])
        for index, frequency in enumerate(frequencies):
            writer.writerow(
                [
                    frequency,
                    s_parameters["s11_db"][index],
                    s_parameters["s21_db"][index],
                    s_parameters["s12_db"][index],
                    s_parameters["s22_db"][index],
                ]
            )


def _write_plot(
    plot_path: Path,
    frequencies: list[float],
    s_parameters: dict[str, list[float]],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_path.parent.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axis = plt.subplots(figsize=(8.4, 5.2), constrained_layout=True)
    for key, label in (
        ("s21_db", "S21"),
        ("s11_db", "S11"),
        ("s12_db", "S12"),
        ("s22_db", "S22"),
    ):
        axis.plot(frequencies, s_parameters[key], linewidth=1.8, label=label)
    axis.set_title("Text-to-GDS RF Network Export")
    axis.set_xlabel("Frequency (GHz)")
    axis.set_ylabel("Magnitude (dB)")
    axis.legend(loc="best")
    axis.grid(True, alpha=0.35)
    fig.savefig(plot_path, dpi=220)
    plt.close(fig)


def _skrf_summary(touchstone_path: Path) -> dict[str, Any] | None:
    if find_spec("skrf") is None:
        return None
    try:
        import skrf as rf

        network = rf.Network(str(touchstone_path))
    except Exception as error:  # pragma: no cover - depends on optional package details.
        return {"available": True, "error": str(error)}
    return {
        "available": True,
        "name": network.name,
        "nports": int(network.nports),
        "frequency_points": int(len(network.f)),
        "z0_ohm": str(network.z0[0][0]) if len(network.f) else None,
    }


def write_rf_network_artifacts(
    simulation: dict[str, Any],
    *,
    touchstone_path: str | Path,
    report_path: str | Path,
    plot_path: str | Path,
    csv_path: str | Path,
    reference_ohm: float = 50.0,
) -> dict[str, Any]:
    """Write Touchstone, plot, CSV, and JSON RF-network artifacts.

    If ``simulation`` contains a ``touchstone_path`` key, that file is used
    directly as a solver Touchstone and validated for passivity and reciprocity
    before any artifacts are written.  A failed validation returns immediately
    with a status="failed" dict — no partial files are left on disk.
    """
    from text_to_gds.rf_validation import validate_touchstone

    touchstone = Path(touchstone_path)
    report = Path(report_path)
    plot = Path(plot_path)
    csv_file = Path(csv_path)
    for path in (touchstone, report, plot, csv_file):
        path.parent.mkdir(parents=True, exist_ok=True)

    # --- If a solver Touchstone is provided, validate it first. ---------------
    solver_ts = simulation.get("touchstone_path")
    if solver_ts is not None:
        ts_file = Path(str(solver_ts))
        if not ts_file.is_file():
            failure = {
                "schema": "text-to-gds.rf-network.v1",
                "status": "failed",
                "reason": "Touchstone file not found at provided path",
                "report_path": str(report),
            }
            report.write_text(json.dumps(failure, indent=2), encoding="utf-8")
            return failure
        validation = validate_touchstone(ts_file)
        if not validation.get("passivity"):
            failure = {
                "schema": "text-to-gds.rf-network.v1",
                "status": "failed",
                "reason": "Touchstone data violates passive power conservation",
                "report_path": str(report),
            }
            report.write_text(json.dumps(failure, indent=2), encoding="utf-8")
            return failure
        # Passed — copy solver file to output location and read S-params from it.
        import shutil
        shutil.copy2(str(ts_file), str(touchstone))
        frequencies, s_parameters = _read_touchstone_data(touchstone)
        source = "solver_touchstone"
        validation_block = {
            "passivity": bool(validation.get("passivity")),
            "reciprocity": bool(validation.get("reciprocity")),
        }
    else:
        if not simulation:
            failure = {
                "schema": "text-to-gds.rf-network.v1",
                "status": "failed",
                "reason": "No Touchstone or simulation result provided",
                "report_path": str(report),
            }
            report.write_text(json.dumps(failure, indent=2), encoding="utf-8")
            return failure
        network = _network_from_simulation(simulation)
        if network is None:
            skipped = {
                "schema": "text-to-gds.rf-network.v1",
                "status": "skipped",
                "reason": (
                    "Simulation result contains no real S-parameter data. "
                    "Run openEMS, JosephsonCircuits.jl, or supply a Touchstone file. "
                    "Synthetic curves are never written."
                ),
                "report_path": str(report),
            }
            report.write_text(json.dumps(skipped, indent=2), encoding="utf-8")
            return skipped
        frequencies, s_parameters, source = network
        touchstone.write_text(
            _touchstone_text(frequencies, s_parameters, reference_ohm=reference_ohm),
            encoding="utf-8",
        )
        validation_block = {"passivity": None, "reciprocity": None}

    _write_csv(csv_file, frequencies, s_parameters)
    _write_plot(plot, frequencies, s_parameters)

    s21 = s_parameters.get("s21_db", [])
    peak_gain = max(s21) if s21 else None
    peak_frequency = frequencies[s21.index(peak_gain)] if peak_gain is not None else None
    physical = simulation.get("physical_performance")
    center_frequency = _center_from_physical(physical if isinstance(physical, dict) else {})
    center_index = min(
        range(len(frequencies)),
        key=lambda index: abs(frequencies[index] - center_frequency),
    ) if frequencies else 0
    result = {
        "schema": "text-to-gds.rf-network.v1",
        "status": "ok",
        "source": source,
        "source_simulation_path": simulation.get("result_path"),
        "touchstone_path": str(touchstone),
        "plot_path": str(plot),
        "csv_path": str(csv_file),
        "report_path": str(report),
        "reference_ohm": reference_ohm,
        "frequency_points": len(frequencies),
        "frequencies_ghz": frequencies,
        "s_parameters_db": s_parameters,
        "peak_s21_gain_db": peak_gain,
        "peak_s21_frequency_ghz": peak_frequency,
        "center_frequency_ghz": center_frequency,
        "center_s21_gain_db": s21[center_index] if s21 else None,
        "bandwidth_3db_mhz": _bandwidth_3db_mhz(frequencies, s21),
        "scikit_rf": _skrf_summary(touchstone),
        "validation": validation_block,
        "model_validity": (
            "Touchstone export is magnitude-only with zero phase unless the upstream "
            "adapter provides complex S-parameters."
        ),
    }
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
