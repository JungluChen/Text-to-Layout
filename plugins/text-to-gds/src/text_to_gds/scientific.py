from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from text_to_gds.plots import _line_series


def _adapter_payload(simulation: dict[str, Any]) -> dict[str, Any]:
    adapter_result = simulation.get("adapter_result")
    if not isinstance(adapter_result, dict):
        return {}
    result = adapter_result.get("result")
    return result if isinstance(result, dict) else {}


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _metric_rows(simulation: dict[str, Any]) -> list[dict[str, Any]]:
    physical = simulation.get("physical_performance", {})
    adapter = _adapter_payload(simulation)
    candidates = [
        ("junction_area_um2", simulation.get("junction_area_um2"), "um^2"),
        ("critical_current_ua", simulation.get("critical_current_ua"), "uA"),
        ("josephson_inductance_ph", simulation.get("josephson_inductance_ph"), "pH"),
        ("center_frequency_ghz", physical.get("center_frequency_ghz"), "GHz"),
        ("estimated_peak_gain_db", physical.get("estimated_peak_gain_db"), "dB"),
        ("bandwidth_3db_mhz", physical.get("bandwidth_3db_mhz"), "MHz"),
        ("loaded_q", physical.get("loaded_q"), ""),
        ("estimated_saturation_power_dbm", physical.get("estimated_saturation_power_dbm"), "dBm"),
        (
            "estimated_input_1db_compression_dbm",
            physical.get("estimated_input_1db_compression_dbm"),
            "dBm",
        ),
        ("quantum_limited_noise_temperature_k", physical.get("quantum_limited_noise_temperature_k"), "K"),
        ("peak_s21_gain_db", adapter.get("peak_s21_gain_db"), "dB"),
        ("peak_s21_frequency_ghz", adapter.get("peak_s21_frequency_ghz"), "GHz"),
        ("center_s21_gain_db", adapter.get("center_s21_gain_db"), "dB"),
    ]
    flux_tuning = physical.get("flux_tuning") if isinstance(physical, dict) else None
    if isinstance(flux_tuning, dict):
        operating = flux_tuning.get("operating_point")
        if isinstance(operating, dict):
            candidates.extend(
                [
                    ("flux_bias_phi0", operating.get("flux_phi0"), "Phi0"),
                    ("flux_tuned_critical_current_ua", operating.get("critical_current_ua"), "uA"),
                    ("flux_tuned_lj_ph", operating.get("josephson_inductance_ph"), "pH"),
                    (
                        "flux_tuned_resonant_frequency_ghz",
                        operating.get("resonant_frequency_ghz"),
                        "GHz",
                    ),
                ]
            )
    rows = []
    for name, value, unit in candidates:
        number = _float_or_none(value)
        if number is not None:
            rows.append({"metric": name, "value": number, "unit": unit})
    return rows


def _write_line_csv(
    csv_path: Path,
    series: list[tuple[str, list[float], list[float], str]],
    x_label: str,
) -> int:
    if not series:
        return 0
    row_count = min(len(item[1]) for item in series)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([x_label or "x", *[item[0] for item in series]])
        for index in range(row_count):
            writer.writerow([series[0][1][index], *[item[2][index] for item in series]])
    return row_count


def _write_metric_csv(csv_path: Path, metrics: list[dict[str, Any]]) -> int:
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "value", "unit"])
        writer.writeheader()
        writer.writerows(metrics)
    return len(metrics)


def write_scientific_plot(
    simulation: dict[str, Any],
    png_path: str | Path,
    *,
    title: str | None = None,
    source_result_path: str | None = None,
) -> dict[str, Any]:
    """Write publication-style PNG/SVG/CSV/JSON evidence for a simulation result."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    png = Path(png_path)
    svg = png.with_suffix(".svg")
    csv_path = png.with_suffix(".csv")
    json_path = png.with_suffix(".json")
    for path in (png, svg, csv_path, json_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    series, default_title, x_label, y_label = _line_series(simulation)
    metrics = _metric_rows(simulation)
    plot_title = title or default_title

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(8.4, 5.2), constrained_layout=True)
    plotted_series: list[str] = []
    row_count = 0

    if series:
        for label, x_values, y_values, unit in series:
            ax.plot(x_values, y_values, marker="o", linewidth=1.8, markersize=3.2, label=label)
            plotted_series.append(f"{label} ({unit})" if unit else label)
        ax.set_xlabel(x_label or "x")
        ax.set_ylabel(y_label or "value")
        ax.legend(loc="best", frameon=True)
        row_count = _write_line_csv(csv_path, series, x_label)
        plot_type = "line"
    else:
        numeric_metrics = metrics[:8]
        if numeric_metrics:
            labels = [row["metric"].replace("_", " ") for row in numeric_metrics]
            values = [row["value"] for row in numeric_metrics]
            ax.barh(labels, values, color="#3866d6")
            ax.invert_yaxis()
            ax.set_xlabel("value")
            plotted_series = [row["metric"] for row in numeric_metrics]
        else:
            ax.text(0.5, 0.5, "No numeric simulation data", ha="center", va="center")
            ax.set_axis_off()
        row_count = _write_metric_csv(csv_path, metrics)
        plot_type = "metric_summary"

    ax.set_title(plot_title)
    ax.tick_params(labelsize=9)
    ax.grid(True, alpha=0.35)
    fig.savefig(png, dpi=220)
    fig.savefig(svg)
    plt.close(fig)

    sidecar = {
        "schema": "text-to-gds.scientific-plot.v0",
        "source_result_path": source_result_path or simulation.get("result_path"),
        "png_path": str(png),
        "svg_path": str(svg),
        "csv_path": str(csv_path),
        "json_path": str(json_path),
        "plot_type": plot_type,
        "title": plot_title,
        "series": plotted_series,
        "row_count": row_count,
        "metrics": metrics,
    }
    json_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    return sidecar


def write_sweep_artifacts(
    sweep: dict[str, Any],
    png_path: str | Path,
) -> dict[str, Any]:
    """Write scientific plot artifacts for a local parameter sweep."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    png = Path(png_path)
    svg = png.with_suffix(".svg")
    csv_path = png.with_suffix(".csv")
    for path in (png, svg, csv_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    rows = [row for row in sweep.get("rows", []) if isinstance(row, dict)]
    parameter = str(sweep.get("sweep_parameter", "parameter"))
    has_flux_frequency = any(
        _float_or_none(row.get("flux_tuned_resonant_frequency_ghz")) is not None for row in rows
    )
    third_metric = (
        ("flux_tuned_resonant_frequency_ghz", "Flux-tuned f0 (GHz)")
        if has_flux_frequency
        else ("bandwidth_3db_mhz", "3 dB bandwidth (MHz)")
    )
    metrics = [
        ("critical_current_ua", "Ic (uA)"),
        ("josephson_inductance_ph", "Lj (pH)"),
        third_metric,
        ("estimated_saturation_power_dbm", "Saturation power (dBm)"),
    ]
    x_values = [_float_or_none(row.get(parameter)) for row in rows]
    valid_indices = [index for index, value in enumerate(x_values) if value is not None]

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = sorted({key for row in rows for key in row})
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(9.2, 6.4), constrained_layout=True)
    plotted: list[str] = []
    for axis, (metric, label) in zip(axes.ravel(), metrics, strict=True):
        points = [
            (float(x_values[index]), _float_or_none(rows[index].get(metric)))
            for index in valid_indices
        ]
        points = [(x, y) for x, y in points if y is not None]
        if points:
            xs, ys = zip(*points, strict=True)
            axis.plot(xs, ys, marker="o", linewidth=1.8, markersize=3.2)
            plotted.append(metric)
        else:
            axis.text(0.5, 0.5, "n/a", ha="center", va="center")
        axis.set_xlabel(parameter)
        axis.set_ylabel(label)
        axis.grid(True, alpha=0.35)
    fig.suptitle(f"Text-to-GDS Parameter Sweep: {parameter}", fontsize=13)
    fig.savefig(png, dpi=220)
    fig.savefig(svg)
    plt.close(fig)

    return {
        "schema": "text-to-gds.sweep-plot.v0",
        "png_path": str(png),
        "svg_path": str(svg),
        "csv_path": str(csv_path),
        "series": plotted,
        "row_count": len(rows),
    }
