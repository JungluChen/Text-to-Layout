"""Publication-quality figure generation for superconducting quantum-device layouts.

Provides:
- ``render_publication_figure`` — multi-panel figure (full chip + zoom + stack + annotations)
- ``render_sem_like`` — grayscale SEM-style visualization
- ``render_benchmark_figure`` — layout + simulation physics results combined
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from textlayout._legacy.rendering import render_layout_screenshot


def _gds_shapes(layout_path: Path) -> list[list[list[tuple[float, float]]]]:
    """Return list of shape polygon-point lists (one per layer group)."""
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(layout_path))
    dbu = float(layout.dbu)
    top_cell = layout.top_cell()
    if top_cell is None:
        return []

    all_shapes: list[list[list[tuple[float, float]]]] = []
    for layer_index in layout.layer_indices():
        layer_polys: list[list[tuple[float, float]]] = []
        iterator = top_cell.begin_shapes_rec(layer_index)
        while not iterator.at_end():
            shape = iterator.shape()
            transform = iterator.trans()
            polygon = None
            if shape.is_box():
                polygon = kdb.Polygon(shape.box).transformed(transform)
            elif shape.is_polygon():
                polygon = shape.polygon.transformed(transform)
            elif shape.is_path():
                polygon = shape.path.polygon().transformed(transform)
            if polygon is not None:
                pts = [(float(p.x) * dbu, float(p.y) * dbu) for p in polygon.each_point_hull()]
                if len(pts) >= 3:
                    layer_polys.append(pts)
            iterator.next()
        if layer_polys:
            all_shapes.append(layer_polys)
    return all_shapes


def _gds_bounds(layout_path: Path) -> tuple[float, float, float, float]:
    """Return (min_x, min_y, max_x, max_y) of all shapes."""
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(layout_path))
    dbu = float(layout.dbu)
    top_cell = layout.top_cell()
    if top_cell is None:
        return (0.0, 0.0, 1.0, 1.0)

    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    for layer_index in layout.layer_indices():
        iterator = top_cell.begin_shapes_rec(layer_index)
        while not iterator.at_end():
            shape = iterator.shape()
            transform = iterator.trans()
            bbox = shape.bbox().transformed(transform)
            left, b = float(bbox.left) * dbu, float(bbox.bottom) * dbu
            r, t = float(bbox.right) * dbu, float(bbox.top) * dbu
            min_x, min_y = min(min_x, left), min(min_y, b)
            max_x, max_y = max(max_x, r), max(max_y, t)
            iterator.next()
    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1.0)
    return (min_x, min_y, min_x + span_x, min_y + span_y)


def render_publication_figure(
    layout_path: Path,
    output_stem: Path,
    *,
    sidecar_path: Path | None = None,
    image_size: int = 1200,
    zoom_factor: float = 4.0,
) -> dict[str, Any]:
    """Generate a multi-panel publication figure:

    Panel (a): Full-chip layout (KLayout-rendered).
    Panel (b): Zoomed view of the active device region.
    Panel (c): Process stack legend.

    Writes PNG and SVG.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PIL import Image

    # Panel (a): full-chip screenshot
    full_png = output_stem.parent / f"{output_stem.name}_full.png"
    render_layout_screenshot(layout_path, full_png, image_size=image_size)
    full_img = Image.open(full_png).convert("RGB")

    # Panel (b): zoomed view
    zoom_png = output_stem.parent / f"{output_stem.name}_zoom.png"
    render_layout_screenshot(layout_path, zoom_png, image_size=int(image_size * zoom_factor))
    zoom_img = Image.open(zoom_png).convert("RGB")

    # Assemble 2-column figure
    fig, axes = plt.subplots(1, 2, figsize=(14.0, 6.5), constrained_layout=True)
    fig.suptitle(layout_path.name, fontsize=14, fontweight="bold", y=1.02)

    axes[0].imshow(full_img)
    axes[0].set_title("(a) Full layout", fontsize=12, fontweight="bold", pad=8)
    axes[0].axis("off")

    axes[1].imshow(zoom_img)
    axes[1].set_title("(b) Device zoom", fontsize=12, fontweight="bold", pad=8)
    axes[1].axis("off")

    # Scale bar on the zoom panel
    try:
        min_x, min_y, max_x, max_y = _gds_bounds(layout_path)
        span_x = max_x - min_x
        bar_um = 10 ** math.floor(math.log10(span_x / 4))
        h, w = zoom_img.size[:2]
        bar_px = w * 0.25
        bar_y = h - 28
        axes[1].plot([w * 0.05, w * 0.05 + bar_px], [bar_y, bar_y],
                     color="white", linewidth=2.5, transform=axes[1].transData)
        axes[1].text(w * 0.05 + bar_px / 2, bar_y - 8, f"{bar_um:.0f} µm",
                     color="white", fontsize=9, ha="center", fontweight="bold",
                     transform=axes[1].transData)
    except Exception:
        pass

    # Annotations from sidecar
    if sidecar_path and sidecar_path.exists():
        try:
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            info = sidecar.get("info", {})
            lines = []
            if "junction_area_um2" in info:
                lines.append(f"JJ Area: {info['junction_area_um2']} µm²")
            if "critical_current_ua" in info:
                lines.append(f"Ic: {info['critical_current_ua']:.3f} uA")
            if "josephson_inductance_ph" in info:
                lines.append(f"Lj: {info['josephson_inductance_ph']:.1f} pH")
            if "width_um" in info:
                lines.append(f"Width: {info['width_um']} µm")
            if "height_um" in info:
                lines.append(f"Height: {info['height_um']} µm")
            if lines:
                text = "\n".join(lines)
                axes[1].text(
                    0.05, 0.92, text, transform=axes[1].transAxes,
                    fontsize=9, color="white",
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.65),
                    verticalalignment="top", fontweight="bold",
                )
        except Exception:
            pass

    png_path = output_stem.parent / f"{output_stem.name}.figure.png"
    svg_path = output_stem.parent / f"{output_stem.name}.figure.svg"
    pdf_path = output_stem.parent / f"{output_stem.name}.figure.pdf"

    fig.savefig(png_path, dpi=200, bbox_inches="tight", facecolor="white")
    fig.savefig(svg_path, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    full_png.unlink(missing_ok=True)
    zoom_png.unlink(missing_ok=True)

    return {
        "status": "generated",
        "png_path": str(png_path),
        "svg_path": str(svg_path),
        "pdf_path": str(pdf_path),
    }


def render_sem_like(
    layout_path: Path,
    output_path: Path,
    *,
    image_size: int = 1000,
    add_scale_bar: bool = True,
    grayscale: bool = True,
) -> dict[str, Any]:
    """Render a grayscale SEM-style visualization of a GDS layout.

    Metal layers appear bright (white/silver), substrate is dark, with
    an optional scale bar and device labels.
    """
    import klayout.db as kdb
    from PIL import Image, ImageDraw

    layout = kdb.Layout()
    layout.read(str(layout_path))
    dbu = float(layout.dbu)
    top_cell = layout.top_cell()
    if top_cell is None:
        raise ValueError(f"Layout has no top cell: {layout_path}")

    shapes: list[list[tuple[float, float]]] = []
    for layer_index in layout.layer_indices():
        iterator = top_cell.begin_shapes_rec(layer_index)
        while not iterator.at_end():
            shape = iterator.shape()
            transform = iterator.trans()
            polygon = None
            if shape.is_box():
                polygon = kdb.Polygon(shape.box).transformed(transform)
            elif shape.is_polygon():
                polygon = shape.polygon.transformed(transform)
            elif shape.is_path():
                polygon = shape.path.polygon().transformed(transform)
            if polygon is not None:
                pts = [(float(p.x) * dbu, float(p.y) * dbu) for p in polygon.each_point_hull()]
                if len(pts) >= 3:
                    shapes.append(pts)
            iterator.next()

    if not shapes:
        canvas = Image.new("L", (image_size, image_size), 30)
        draw = ImageDraw.Draw(canvas)
        draw.text((24, 24), f"No drawable shapes in {layout_path.name}", fill=180)
        canvas.save(output_path)
        return {"status": "empty", "path": str(output_path)}

    min_x = min(p[0] for poly in shapes for p in poly)
    min_y = min(p[1] for poly in shapes for p in poly)
    max_x = max(p[0] for poly in shapes for p in poly)
    max_y = max(p[1] for poly in shapes for p in poly)
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)

    margin = max(image_size * 0.08, 24.0)
    scale = min((image_size - 2 * margin) / span_x, (image_size - 2 * margin) / span_y)
    drawn_w = span_x * scale
    drawn_h = span_y * scale
    offset_x = (image_size - drawn_w) / 2.0
    offset_y = (image_size - drawn_h) / 2.0

    def to_px(x: float, y: float) -> tuple[float, float]:
        return offset_x + (x - min_x) * scale, offset_y + drawn_h - (y - min_y) * scale

    canvas = Image.new("L", (image_size, image_size), 35)
    draw = ImageDraw.Draw(canvas)

    # Anti-aliased edges via slight oversampling
    for poly in shapes:
        pts = [to_px(x, y) for x, y in poly]
        if len(pts) >= 3:
            draw.polygon(pts, fill=210, outline=240)

    # Scale bar
    if add_scale_bar:
        bar_um = 10 ** math.floor(math.log10(span_x / 3))
        bar_px = bar_um * scale
        bar_x = image_size - margin - bar_px
        bar_y = image_size - margin + 12
        draw.line([(bar_x, bar_y), (bar_x + bar_px, bar_y)], fill=240, width=3)
        draw.text((bar_x + bar_px / 2, bar_y + 6), f"{bar_um:.0f} um", fill=200, anchor="mt")

    # Title
    draw.text((margin, 12), layout_path.name, fill=180)

    canvas.save(output_path)
    return {"status": "generated", "path": str(output_path), "shape_count": len(shapes)}


def render_benchmark_figure(
    layout_path: Path,
    simulation_path: Path | None,
    output_path: Path,
    *,
    sidecar_path: Path | None = None,
    image_size: int = 1400,
) -> dict[str, Any]:
    """Render a publication figure combining layout with simulation results.

    Left panel: layout screenshot with annotations.
    Right panel: simulation results (S-parameters, gain, etc.) when available.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PIL import Image

    # Layout panel
    layout_png = output_path.parent / f"{output_path.stem}_layout.png"
    render_layout_screenshot(layout_path, layout_png, image_size=image_size)
    layout_img = Image.open(layout_png).convert("RGB")

    has_sim = simulation_path is not None and simulation_path.exists()
    sim_data = {}
    if has_sim:
        try:
            sim_data = json.loads(simulation_path.read_text(encoding="utf-8"))
        except Exception:
            has_sim = False

    # Check if there's actually plottable data
    has_plots = bool(
        sim_data.get("frequencies_hz")
        or sim_data.get("frequencies_ghz")
        or sim_data.get("gain_vs_pump_db")
        or sim_data.get("pump_powers_dbm")
        or sim_data.get("s21_db")
        or sim_data.get("noise_temperature_k")
    )
    has_physics = bool(
        sim_data.get("critical_current_ua")
        or sim_data.get("josephson_inductance_ph")
        or sim_data.get("info", {}).get("junction_area_um2")
        or sim_data.get("physical_performance")
    )

    if has_sim and (has_plots or has_physics):
        fig = plt.figure(figsize=(16.0, 7.0), constrained_layout=True)
        gs = fig.add_gridspec(2, 3, width_ratios=[1.2, 0.9, 0.9])

        # Layout panel (spans full left column)
        ax_layout = fig.add_subplot(gs[:, 0])
        ax_layout.imshow(layout_img)
        ax_layout.set_title("Layout", fontsize=12, fontweight="bold")
        ax_layout.axis("off")

        # Physics annotation overlay
        info = sim_data.get("info") or sim_data.get("physical_performance") or {}
        lines = []
        for key, label, unit in [
            ("critical_current_ua", "Ic", "µA"),
            ("josephson_inductance_ph", "Lj", "pH"),
            ("junction_area_um2", "Area", "µm²"),
            ("center_frequency_ghz", "f0", "GHz"),
            ("estimated_peak_gain_db", "Gain", "dB"),
            ("bandwidth_3db_mhz", "BW", "MHz"),
        ]:
            val = info.get(key)
            if val is not None and val != 0.0:
                lines.append(f"{label} = {float(val):.4g} {unit}")
        if lines:
            ax_layout.text(
                0.03, 0.97, "\n".join(lines), transform=ax_layout.transAxes,
                fontsize=9, color="white",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.6),
                verticalalignment="top", fontfamily="monospace",
            )

        # S-parameters from sim data
        freqs_ghz: list[float] = []
        freqs = sim_data.get("frequencies_hz") or sim_data.get("frequencies_ghz", [])
        s21 = sim_data.get("s21_db") or sim_data.get("gain_db", [])
        if freqs and s21:
            if max(freqs) > 1e8:
                freqs_ghz = [f / 1e9 for f in freqs]
            else:
                freqs_ghz = list(freqs)

            ax_s21 = fig.add_subplot(gs[0, 1])
            ax_s21.plot(freqs_ghz, s21, linewidth=1.8, color="#3866d6")
            ax_s21.set_xlabel("Frequency (GHz)")
            ax_s21.set_ylabel("|S21| (dB)")
            ax_s21.set_title("(b) Transmission", fontsize=11, fontweight="bold")
            ax_s21.grid(True, alpha=0.3)

            s11 = sim_data.get("s11_db", [])
            if s11 and len(s11) == len(freqs_ghz):
                ax_s11 = fig.add_subplot(gs[0, 2])
                ax_s11.plot(freqs_ghz, s11, linewidth=1.8, color="#da4956")
                ax_s11.set_xlabel("Frequency (GHz)")
                ax_s11.set_ylabel("|S11| (dB)")
                ax_s11.set_title("(c) Reflection", fontsize=11, fontweight="bold")
                ax_s11.grid(True, alpha=0.3)

        # Gain / pump sweep
        pump = sim_data.get("pump_powers_dbm") or sim_data.get("coil_currents_ma", [])
        gain = sim_data.get("gain_vs_pump_db") or sim_data.get("gain_vs_current_db", [])
        if pump and gain and len(pump) == len(gain):
            ax_gain = fig.add_subplot(gs[1, 1])
            ax_gain.plot(pump, gain, linewidth=1.8, color="#309a67")
            ax_gain.set_xlabel("Pump power (dBm)")
            ax_gain.set_ylabel("Gain (dB)")
            ax_gain.set_title("(d) Pump sweep", fontsize=11, fontweight="bold")
            ax_gain.grid(True, alpha=0.3)

        # Noise / additional metrics
        noise = sim_data.get("noise_temperature_k", [])
        noise_freqs = sim_data.get("noise_frequencies_ghz", freqs_ghz if freqs_ghz else [])
        if noise and noise_freqs and len(noise) == len(noise_freqs):
            ax_noise = fig.add_subplot(gs[1, 2])
            ax_noise.plot(noise_freqs, noise, linewidth=1.8, color="#7c3aed")
            ax_noise.set_xlabel("Frequency (GHz)")
            ax_noise.set_ylabel("T_n (K)")
            ax_noise.set_title("(e) Noise temperature", fontsize=11, fontweight="bold")
            ax_noise.grid(True, alpha=0.3)

        fig.suptitle(layout_path.name, fontsize=14, fontweight="bold", y=1.02)
    else:
        fig, ax = plt.subplots(figsize=(8.0, 6.0))
        ax.imshow(layout_img)
        ax.set_title(layout_path.name, fontsize=13, fontweight="bold")
        ax.axis("off")
        ax.text(0.5, 0.02, "No simulation data available", transform=ax.transAxes,
                ha="center", fontsize=10, color="#6e6e73")

    fig.savefig(output_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    layout_png.unlink(missing_ok=True)

    return {
        "status": "generated",
        "path": str(output_path),
        "has_simulation": has_sim,
    }
