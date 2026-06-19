from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


Series = tuple[str, list[float], list[float], str]

PLOT_COLORS = ["#0071e3", "#34c759", "#ff9f0a", "#ff375f"]


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _adapter_payload(simulation: dict[str, Any]) -> dict[str, Any]:
    adapter_result = simulation.get("adapter_result")
    if not isinstance(adapter_result, dict):
        return {}
    result = adapter_result.get("result")
    return result if isinstance(result, dict) else {}


def _finite_values(values: list[Any]) -> list[float]:
    finite: list[float] = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            finite.append(number)
    return finite


def _line_series(simulation: dict[str, Any]) -> tuple[list[Series], str, str, str]:
    physical = simulation.get("physical_performance")
    if isinstance(physical, dict):
        flux_tuning = physical.get("flux_tuning")
        if isinstance(flux_tuning, dict):
            rows = flux_tuning.get("sweep")
            if isinstance(rows, list) and rows:
                frequency_pairs = [
                    (float(row["flux_phi0"]), float(row["resonant_frequency_ghz"]))
                    for row in rows
                    if isinstance(row, dict)
                    and row.get("flux_phi0") is not None
                    and row.get("resonant_frequency_ghz") is not None
                ]
                if frequency_pairs:
                    flux = [item[0] for item in frequency_pairs]
                    frequency = [item[1] for item in frequency_pairs]
                    return [
                        ("Resonance", flux, frequency, "GHz")
                    ], "SQUID Flux Tuning", "Flux bias (Phi/Phi0)", "Frequency (GHz)"
                current_pairs = [
                    (float(row["flux_phi0"]), float(row["critical_current_ua"]))
                    for row in rows
                    if isinstance(row, dict)
                    and row.get("flux_phi0") is not None
                    and row.get("critical_current_ua") is not None
                ]
                if current_pairs:
                    flux = [item[0] for item in current_pairs]
                    critical_current = [item[1] for item in current_pairs]
                    return [
                        ("Ic_eff", flux, critical_current, "uA")
                    ], "SQUID Critical Current Modulation", "Flux bias (Phi/Phi0)", "Ic (uA)"

    payload = _adapter_payload(simulation)
    frequencies = _finite_values(payload.get("frequencies_ghz", []))
    s_parameters = payload.get("s_parameters_db")
    if frequencies and isinstance(s_parameters, dict):
        series = []
        for label, key in [
            ("S21", "s21_db"),
            ("S11", "s11_db"),
            ("S12", "s12_db"),
            ("S22", "s22_db"),
        ]:
            values = _finite_values(s_parameters.get(key, []))
            if len(values) == len(frequencies):
                series.append((label, frequencies, values, "dB"))
        if series:
            return series, "JosephsonCircuits S-Parameters", "Frequency (GHz)", "Gain (dB)"

    reflection = _finite_values(payload.get("reflection_gain_db", []))
    if frequencies and len(reflection) == len(frequencies):
        return [
            ("S11 reflection", frequencies, reflection, "dB")
        ], "JosephsonCircuits Reflection Gain", "Frequency (GHz)", "Gain (dB)"

    adapter_result = simulation.get("adapter_result")
    if isinstance(adapter_result, dict):
        rows = adapter_result.get("parsed_rows")
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            keys = [key for key in rows[0] if isinstance(rows[0].get(key), (int, float))]
            if len(keys) >= 2:
                x_values = _finite_values([row.get(keys[0]) for row in rows])
                y_values = _finite_values([row.get(keys[1]) for row in rows])
                if len(x_values) == len(y_values) and x_values:
                    adapter_name = str(adapter_result.get("adapter") or simulation.get("adapter") or "Adapter")
                    title = (
                        "ngspice Simulation Result"
                        if adapter_name.lower() == "ngspice"
                        else "JoSIM Transient Result"
                    )
                    return [
                        (keys[1], x_values, y_values, "")
                    ], title, keys[0], keys[1]

    return [], "Ideal Josephson Junction", "", ""


def _nice_bounds(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 1.0
    lower = min(values)
    upper = max(values)
    if math.isclose(lower, upper):
        spread = abs(lower) * 0.1 or 1.0
        return lower - spread, upper + spread
    padding = (upper - lower) * 0.08
    return lower - padding, upper + padding


def _draw_line_plot(
    draw: ImageDraw.ImageDraw,
    series: list[Series],
    *,
    bounds: tuple[int, int, int, int],
    title: str,
    x_label: str,
    y_label: str,
) -> None:
    left, top, right, bottom = bounds
    title_font = _font(30, bold=True)
    label_font = _font(18)
    small_font = _font(15)

    draw.text((left, top - 58), title, fill="#1d1d1f", font=title_font)
    all_x = [value for _, x_values, _, _ in series for value in x_values]
    all_y = [value for _, _, y_values, _ in series for value in y_values]
    x_min, x_max = _nice_bounds(all_x)
    y_min, y_max = _nice_bounds(all_y)

    draw.rounded_rectangle((left, top, right, bottom), radius=20, fill="#ffffff", outline="#d2d2d7")
    axis_left = left + 78
    axis_right = right - 32
    axis_top = top + 34
    axis_bottom = bottom - 66
    draw.line((axis_left, axis_bottom, axis_right, axis_bottom), fill="#86868b", width=2)
    draw.line((axis_left, axis_top, axis_left, axis_bottom), fill="#86868b", width=2)

    for tick in range(5):
        ratio = tick / 4
        x = axis_left + (axis_right - axis_left) * ratio
        y = axis_bottom - (axis_bottom - axis_top) * ratio
        x_value = x_min + (x_max - x_min) * ratio
        y_value = y_min + (y_max - y_min) * ratio
        draw.line((x, axis_bottom, x, axis_bottom + 7), fill="#86868b", width=1)
        draw.line((axis_left - 7, y, axis_left, y), fill="#86868b", width=1)
        draw.text((x - 24, axis_bottom + 12), f"{x_value:.3g}", fill="#515154", font=small_font)
        draw.text((left + 14, y - 9), f"{y_value:.3g}", fill="#515154", font=small_font)
        if tick not in {0, 4}:
            draw.line((axis_left, y, axis_right, y), fill="#f5f5f7", width=1)

    def point(x_value: float, y_value: float) -> tuple[float, float]:
        x_ratio = 0.0 if math.isclose(x_min, x_max) else (x_value - x_min) / (x_max - x_min)
        y_ratio = 0.0 if math.isclose(y_min, y_max) else (y_value - y_min) / (y_max - y_min)
        return (
            axis_left + x_ratio * (axis_right - axis_left),
            axis_bottom - y_ratio * (axis_bottom - axis_top),
        )

    for index, (label, x_values, y_values, unit) in enumerate(series):
        color = PLOT_COLORS[index % len(PLOT_COLORS)]
        points = [point(x_value, y_value) for x_value, y_value in zip(x_values, y_values, strict=True)]
        if len(points) == 1:
            x, y = points[0]
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=color)
        elif points:
            draw.line(points, fill=color, width=4, joint="curve")
        legend_x = axis_left + index * 150
        legend_y = bottom - 38
        draw.rounded_rectangle((legend_x, legend_y, legend_x + 18, legend_y + 18), radius=5, fill=color)
        suffix = f" ({unit})" if unit else ""
        draw.text((legend_x + 26, legend_y - 1), f"{label}{suffix}", fill="#1d1d1f", font=small_font)

    draw.text(((axis_left + axis_right) / 2 - 70, bottom - 34), x_label, fill="#515154", font=label_font)
    draw.text((left + 12, top + 12), y_label, fill="#515154", font=label_font)


def _draw_summary(
    draw: ImageDraw.ImageDraw,
    simulation: dict[str, Any],
    *,
    bounds: tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = bounds
    title_font = _font(30, bold=True)
    label_font = _font(18)
    value_font = _font(28, bold=True)
    draw.text((left, top - 58), "Ideal Josephson Junction", fill="#1d1d1f", font=title_font)
    draw.rounded_rectangle((left, top, right, bottom), radius=24, fill="#ffffff", outline="#d2d2d7")
    cards = [
        ("Junction area", simulation.get("junction_area_um2"), "um^2"),
        ("Critical current", simulation.get("critical_current_ua"), "uA"),
        ("Josephson inductance", simulation.get("josephson_inductance_ph"), "pH"),
        ("Shunt capacitance", simulation.get("shunt_capacitance_ff"), "fF"),
    ]
    card_width = (right - left - 72) / 2
    card_height = (bottom - top - 72) / 2
    for index, (label, value, unit) in enumerate(cards):
        col = index % 2
        row = index // 2
        x0 = left + 24 + col * (card_width + 24)
        y0 = top + 24 + row * (card_height + 24)
        x1 = x0 + card_width
        y1 = y0 + card_height
        draw.rounded_rectangle((x0, y0, x1, y1), radius=20, fill="#f5f5f7")
        draw.text((x0 + 22, y0 + 22), label, fill="#515154", font=label_font)
        rendered = "n/a" if value is None else f"{float(value):.6g} {unit}"
        draw.text((x0 + 22, y0 + 60), rendered, fill="#1d1d1f", font=value_font)


def write_simulation_plot(
    simulation: dict[str, Any],
    output_path: str | Path,
    *,
    width: int = 1200,
    height: int = 760,
) -> dict[str, Any]:
    """Draw a local PNG plot for simulation output using only Python/Pillow."""
    output = Path(output_path)
    image = Image.new("RGB", (width, height), "#f5f5f7")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 24, width - 24, height - 24), radius=34, fill="#fbfbfd")

    series, title, x_label, y_label = _line_series(simulation)
    if series:
        _draw_line_plot(
            draw,
            series,
            bounds=(72, 136, width - 72, height - 74),
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
        plot_type = "line"
        plotted_series = [label for label, _, _, _ in series]
    else:
        _draw_summary(draw, simulation, bounds=(72, 136, width - 72, height - 74))
        plot_type = "summary"
        plotted_series = []

    draw.text((72, 54), "Text-to-GDS Simulation Plot", fill="#1d1d1f", font=_font(24, bold=True))
    draw.text(
        (72, 86),
        "Local Python-rendered evidence for circuit iteration; not signoff.",
        fill="#6e6e73",
        font=_font(16),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return {
        "schema": "text-to-gds.simulation-plot.v0",
        "plot_path": str(output),
        "plot_type": plot_type,
        "series": plotted_series,
    }
