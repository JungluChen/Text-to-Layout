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


def _synthetic_frequency_response(
    simulation: dict[str, Any],
    *,
    points: int = 101,
) -> tuple[list[float], dict[str, list[float]], str]:
    physical = simulation.get("physical_performance")
    physical = physical if isinstance(physical, dict) else {}
    center_ghz = _center_from_physical(physical)
    bandwidth_mhz = _finite_float(physical.get("bandwidth_3db_mhz")) or 500.0
    peak_gain_db = _finite_float(physical.get("estimated_peak_gain_db")) or 0.0
    bandwidth_ghz = max(bandwidth_mhz / 1000.0, 0.001)
    span_ghz = max(2.5 * bandwidth_ghz, 0.25)
    start = max(center_ghz - span_ghz / 2.0, 0.001)
    stop = center_ghz + span_ghz / 2.0
    step = (stop - start) / float(points - 1)
    frequencies = [start + step * index for index in range(points)]

    s21 = []
    s11 = []
    for frequency in frequencies:
        normalized = 2.0 * (frequency - center_ghz) / bandwidth_ghz
        rolloff_db = 10.0 * math.log10(1.0 + normalized**2)
        gain = peak_gain_db - rolloff_db
        s21.append(gain)
        s11.append(min(-3.0, -12.0 + 0.35 * rolloff_db))

    return (
        frequencies,
        {
            "s11_db": s11,
            "s21_db": s21,
            "s12_db": list(s21),
            "s22_db": list(s11),
        },
        "layout_surrogate",
    )


def _network_from_simulation(
    simulation: dict[str, Any],
) -> tuple[list[float], dict[str, list[float]], str]:
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

    return _synthetic_frequency_response(simulation)


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
    """Write Touchstone, plot, CSV, and JSON RF-network artifacts."""
    touchstone = Path(touchstone_path)
    report = Path(report_path)
    plot = Path(plot_path)
    csv_file = Path(csv_path)
    for path in (touchstone, report, plot, csv_file):
        path.parent.mkdir(parents=True, exist_ok=True)

    frequencies, s_parameters, source = _network_from_simulation(simulation)
    touchstone.write_text(
        _touchstone_text(frequencies, s_parameters, reference_ohm=reference_ohm),
        encoding="utf-8",
    )
    _write_csv(csv_file, frequencies, s_parameters)
    _write_plot(plot, frequencies, s_parameters)

    s21 = s_parameters["s21_db"]
    peak_gain = max(s21) if s21 else None
    peak_frequency = frequencies[s21.index(peak_gain)] if peak_gain is not None else None
    physical = simulation.get("physical_performance")
    center_frequency = _center_from_physical(physical if isinstance(physical, dict) else {})
    center_index = min(
        range(len(frequencies)),
        key=lambda index: abs(frequencies[index] - center_frequency),
    )
    result = {
        "schema": "text-to-gds.rf-network.v0",
        "source_simulation_path": simulation.get("result_path"),
        "source": source,
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
        "model_validity": (
            "Touchstone export is magnitude-only with zero phase unless the upstream "
            "adapter provides complex S-parameters."
        ),
    }
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
