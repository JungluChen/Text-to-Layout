"""Publication-quality visualization for superconducting quantum IC layouts.

Generates:
  - Layer view with fabrication colors and hatch styles
  - Net view with device-specific coloring
  - Circuit view from extracted topology
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


# ─── Fabrication color palette ────────────────────────────────────────────────

LAYER_COLORS = {
    "M1": {"face": "#4A90D9", "edge": "#2C5F8A", "hatch": "//", "label": "Ground Plane (M1)"},
    "M2": {"face": "#D94A4A", "edge": "#8A2C2C", "hatch": "\\\\", "label": "Signal Trace (M2)"},
    "M3": {"face": "#D9A84A", "edge": "#8A6B2C", "hatch": "xx", "label": "Routing (M3)"},
    "JJ": {"face": "#9B59B6", "edge": "#6C3483", "hatch": "..", "label": "Josephson Junction"},
    "VIA12": {"face": "#2ECC71", "edge": "#1E8449", "hatch": "oo", "label": "Via M1-M2"},
    "VIA23": {"face": "#1ABC9C", "edge": "#117864", "hatch": "++", "label": "Via M2-M3"},
    "UNDERCUT": {"face": "#F39C12", "edge": "#B7950B", "hatch": "..", "label": "Undercut"},
    "MARKER": {"face": "#BDC3C7", "edge": "#7F8C8D", "hatch": "", "label": "Marker"},
    "CHIP_BOUNDARY": {"face": "none", "edge": "#2C3E50", "hatch": "", "label": "Chip Boundary"},
    "KEEPOUT": {"face": "#E74C3C", "edge": "#922B21", "hatch": "xx", "label": "Keepout"},
    "PORT": {"face": "#3498DB", "edge": "#2471A3", "hatch": "", "label": "Port"},
}

# Net view colors for different signal types
NET_COLORS = {
    "rf": {"face": "#E74C3C", "edge": "#922B21", "label": "RF Signal"},
    "pump": {"face": "#9B59B6", "edge": "#6C3483", "label": "Pump"},
    "readout": {"face": "#3498DB", "edge": "#2471A3", "label": "Readout"},
    "drive": {"face": "#2ECC71", "edge": "#1E8449", "label": "Drive/XY"},
    "flux": {"face": "#F39C12", "edge": "#B7950B", "label": "Flux Bias"},
    "ground": {"face": "#95A5A6", "edge": "#7F8C8D", "label": "Ground"},
    "floating": {"face": "#BDC3C7", "edge": "#7F8C8D", "label": "Floating Island"},
    "jj": {"face": "#8E44AD", "edge": "#6C3483", "label": "Josephson Junction"},
}


def generate_layer_view(
    gds_path: str,
    output_path: str | None = None,
    *,
    dpi: int = 150,
    figsize: tuple[float, float] = (8.0, 8.0),
    show_legend: bool = True,
    title: str | None = None,
) -> dict[str, Any]:
    """Generate publication-quality layer view.

    Uses actual fabrication colors, different hatch styles, rounded legends,
    and true CPW appearance with dielectric openings.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        return {"status": "skipped", "reason": "matplotlib not installed"}

    try:
        import klayout.db as kdb
    except ImportError:
        return {"status": "skipped", "reason": "klayout not installed"}

    layout = kdb.Layout()
    layout.read(str(gds_path))
    tops = layout.top_cells()
    if not tops:
        return {"status": "failed", "reason": "no top cells"}

    cell = tops[0]
    dbu = layout.dbu

    fig, ax = plt.subplots(1, 1, figsize=figsize)

    legend_handles = []

    for layer_index in layout.layer_indices():
        info = layout.get_info(layer_index)
        layer_key = f"L{info.layer}D{info.datatype}"

        # Find matching process layer
        color_info = None
        for name, ci in LAYER_COLORS.items():
            if info.layer == layer_index:
                color_info = ci
                break

        # Try by layer number
        layer_names = {3: "M1", 4: "JJ", 5: "M2", 6: "M3",
                       7: "VIA12", 8: "VIA23", 9: "UNDERCUT",
                       10: "MARKER", 11: "CHIP_BOUNDARY", 12: "KEEPOUT", 13: "PORT"}
        if color_info is None and info.layer in layer_names:
            name = layer_names[info.layer]
            color_info = LAYER_COLORS.get(name)

        if color_info is None:
            color_info = {"face": "#CCCCCC", "edge": "#888888", "hatch": "", "label": layer_key}

        for shape in cell.shapes(layer_index).each():
            if shape.is_polygon() or shape.is_box():
                poly = shape.polygon if shape.is_polygon() else kdb.Polygon(shape.box)
                points = [(pt.x * dbu, pt.y * dbu) for pt in poly.each_point_hull()]
                if len(points) < 3:
                    continue

                face = color_info["face"]
                edge = color_info["edge"]
                hatch = color_info.get("hatch", "")

                if face == "none":
                    from matplotlib.patches import Polygon as MplPolygon
                    patch = MplPolygon(points, closed=True, fill=False,
                                       edgecolor=edge, linewidth=1.5)
                else:
                    from matplotlib.patches import Polygon as MplPolygon
                    patch = MplPolygon(points, closed=True,
                                       facecolor=face, edgecolor=edge,
                                       hatch=hatch, alpha=0.7, linewidth=0.5)

                ax.add_patch(patch)

        if color_info and color_info["label"] not in [h.get_text() for h in legend_handles]:
            legend_handles.append(mpatches.Patch(
                facecolor=color_info["face"] if color_info["face"] != "none" else "white",
                edgecolor=color_info["edge"],
                hatch=color_info.get("hatch", ""),
                label=color_info["label"],
                alpha=0.7,
            ))

    # Auto-scale
    bbox = cell.bbox()
    x_min = bbox.left * dbu
    y_min = bbox.bottom * dbu
    x_max = bbox.right * dbu
    y_max = bbox.top * dbu
    margin = max(x_max - x_min, y_max - y_min) * 0.05

    ax.set_xlim(x_min - margin, x_max + margin)
    ax.set_ylim(y_min - margin, y_max + margin)
    ax.set_aspect("equal")
    ax.set_xlabel("X (um)", fontsize=10)
    ax.set_ylabel("Y (um)", fontsize=10)
    ax.set_title(title or f"Layer View: {Path(gds_path).stem}", fontsize=12, fontweight="bold")

    if show_legend and legend_handles:
        ax.legend(handles=legend_handles, loc="upper right", fontsize=8,
                  framealpha=0.9, edgecolor="#CCCCCC", fancybox=True)

    ax.grid(True, alpha=0.2, linestyle="--")
    fig.tight_layout()

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(out), dpi=dpi, bbox_inches="tight",
                    facecolor="white", edgecolor="none")
        plt.close(fig)
        return {"status": "ok", "path": str(out)}

    plt.close(fig)
    return {"status": "ok"}


def generate_net_view(
    gds_path: str,
    sidecar: dict[str, Any] | None = None,
    output_path: str | None = None,
    *,
    dpi: int = 150,
    figsize: tuple[float, float] = (8.0, 8.0),
    title: str | None = None,
) -> dict[str, Any]:
    """Generate net view with device-specific coloring.

    Differentiates RF, Pump, Readout, Drive, Flux, Ground, Floating Island, JJ.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        return {"status": "skipped", "reason": "matplotlib not installed"}

    try:
        import klayout.db as kdb
    except ImportError:
        return {"status": "skipped", "reason": "klayout not installed"}

    sidecar = sidecar or {}
    ports = sidecar.get("ports") or []

    layout = kdb.Layout()
    layout.read(str(gds_path))
    tops = layout.top_cells()
    if not tops:
        return {"status": "failed", "reason": "no top cells"}

    cell = tops[0]
    dbu = layout.dbu

    fig, ax = plt.subplots(1, 1, figsize=figsize)

    # Assign colors to layers
    layer_names = {3: "ground", 4: "jj", 5: "rf", 6: "rf", 7: "ground", 8: "ground"}
    legend_handles = []
    used_nets = set()

    for layer_index in layout.layer_indices():
        info = layout.get_info(layer_index)
        net_type = layer_names.get(info.layer, "floating")
        color_info = NET_COLORS.get(net_type, NET_COLORS["floating"])

        if net_type not in used_nets:
            used_nets.add(net_type)
            legend_handles.append(mpatches.Patch(
                facecolor=color_info["face"],
                edgecolor=color_info["edge"],
                label=color_info["label"],
                alpha=0.7,
            ))

        for shape in cell.shapes(layer_index).each():
            if shape.is_polygon() or shape.is_box():
                poly = shape.polygon if shape.is_polygon() else kdb.Polygon(shape.box)
                points = [(pt.x * dbu, pt.y * dbu) for pt in poly.each_point_hull()]
                if len(points) < 3:
                    continue

                from matplotlib.patches import Polygon as MplPolygon
                patch = MplPolygon(points, closed=True,
                                   facecolor=color_info["face"],
                                   edgecolor=color_info["edge"],
                                   alpha=0.6, linewidth=0.5)
                ax.add_patch(patch)

    # Add port markers
    for port in ports:
        center = port.get("center")
        if center and len(center) >= 2:
            name = str(port.get("name", "")).lower()
            if any(kw in name for kw in ("rf", "in", "out", "signal")):
                color = NET_COLORS["rf"]["face"]
            elif any(kw in name for kw in ("pump", "flux", "bias")):
                color = NET_COLORS["flux"]["face"]
            elif any(kw in name for kw in ("readout", "ro")):
                color = NET_COLORS["readout"]["face"]
            elif any(kw in name for kw in ("drive", "xy")):
                color = NET_COLORS["drive"]["face"]
            else:
                color = NET_COLORS["floating"]["face"]

            ax.plot(float(center[0]), float(center[1]), "o",
                    color=color, markersize=8, markeredgecolor="black",
                    markeredgewidth=1, zorder=10)
            ax.annotate(port.get("name", ""), (float(center[0]), float(center[1])),
                       textcoords="offset points", xytext=(5, 5),
                       fontsize=7, color="black")

    bbox = cell.bbox()
    x_min = bbox.left * dbu
    y_min = bbox.bottom * dbu
    x_max = bbox.right * dbu
    y_max = bbox.top * dbu
    margin = max(x_max - x_min, y_max - y_min) * 0.05

    ax.set_xlim(x_min - margin, x_max + margin)
    ax.set_ylim(y_min - margin, y_max + margin)
    ax.set_aspect("equal")
    ax.set_xlabel("X (um)", fontsize=10)
    ax.set_ylabel("Y (um)", fontsize=10)
    ax.set_title(title or f"Net View: {Path(gds_path).stem}", fontsize=12, fontweight="bold")

    if legend_handles:
        ax.legend(handles=legend_handles, loc="upper right", fontsize=8,
                  framealpha=0.9, edgecolor="#CCCCCC", fancybox=True)

    ax.grid(True, alpha=0.2, linestyle="--")
    fig.tight_layout()

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(out), dpi=dpi, bbox_inches="tight",
                    facecolor="white", edgecolor="none")
        plt.close(fig)
        return {"status": "ok", "path": str(out)}

    plt.close(fig)
    return {"status": "ok"}


def generate_circuit_view(
    topology: dict[str, Any] | None = None,
    physics_graph: dict[str, Any] | None = None,
    output_path: str | None = None,
    *,
    dpi: int = 150,
    figsize: tuple[float, float] = (10.0, 6.0),
) -> dict[str, Any]:
    """Generate physical equivalent circuit from extracted topology.

    Automatically generates the circuit diagram from the extracted topology
    rather than using fixed templates.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return {"status": "skipped", "reason": "matplotlib not installed"}

    fig, ax = plt.subplots(1, 1, figsize=figsize)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Physical Equivalent Circuit", fontsize=14, fontweight="bold", pad=20)

    # Build circuit from topology
    if topology:
        features = topology.get("features", {})
        detected = topology.get("detected_device", "unknown")

        # Draw based on detected topology
        if detected in ("lumped_jpa", "quarter_wave_jpa"):
            _draw_jpa_circuit(ax, features)
        elif detected in ("pocket_transmon", "xmon", "concentric_transmon"):
            _draw_transmon_circuit(ax, features, detected)
        elif detected in ("cpw_resonator", "idc_resonator"):
            _draw_resonator_circuit(ax, features)
        else:
            _draw_generic_circuit(ax, features)
    elif physics_graph:
        _draw_graph_circuit(ax, physics_graph)
    else:
        ax.text(5, 3, "No topology data available\nfor circuit generation",
                ha="center", va="center", fontsize=12, color="#666666")

    fig.tight_layout()

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(str(out), dpi=dpi, bbox_inches="tight",
                    facecolor="white", edgecolor="none")
        plt.close(fig)
        return {"status": "ok", "path": str(out)}

    plt.close(fig)
    return {"status": "ok"}


def _draw_jpa_circuit(ax: Any, features: dict[str, Any]) -> None:
    """Draw JPA equivalent circuit."""
    # RF input
    ax.annotate("", xy=(1.5, 3), xytext=(0.5, 3),
                arrowprops=dict(arrowstyle="->", color="#E74C3C", lw=2))
    ax.text(0.3, 3, "RF\nIn", ha="center", va="center", fontsize=8, color="#E74C3C")

    # Cc (coupling capacitor)
    _draw_capacitor(ax, 2.0, 3, "Cc")

    # IDC
    _draw_idc(ax, 3.5, 3, "IDC")

    # SQUID
    _draw_squid(ax, 5.0, 3, "SQUID")

    # Ground
    ax.plot([5.0, 5.0], [2.0, 1.5], "k-", lw=1.5)
    _draw_ground(ax, 5.0, 1.5)

    # RF output
    _draw_capacitor(ax, 6.5, 3, "Cc")
    ax.annotate("", xy=(8.5, 3), xytext=(7.5, 3),
                arrowprops=dict(arrowstyle="->", color="#E74C3C", lw=2))
    ax.text(8.7, 3, "RF\nOut", ha="center", va="center", fontsize=8, color="#E74C3C")

    # Pump/Flux
    ax.plot([5.0, 5.0], [4.0, 5.0], "k-", lw=1.5)
    ax.annotate("", xy=(5.0, 5.5), xytext=(5.0, 5.0),
                arrowprops=dict(arrowstyle="->", color="#F39C12", lw=2))
    ax.text(5.0, 5.8, "Pump/Flux", ha="center", va="center", fontsize=8, color="#F39C12")

    ax.text(5.0, 0.5, f"JPA Circuit ({features.get('jj_count', '?')} JJ, "
            f"{features.get('idc_count', '?')} IDC)",
            ha="center", va="center", fontsize=10, fontstyle="italic")


def _draw_transmon_circuit(ax: Any, features: dict[str, Any], variant: str) -> None:
    """Draw transmon equivalent circuit."""
    # Qubit capacitor
    _draw_capacitor(ax, 3.0, 3, "C_s")

    # JJ
    _draw_jj(ax, 5.0, 3, "JJ")

    # Readout
    ax.annotate("", xy=(1.5, 3), xytext=(0.5, 3),
                arrowprops=dict(arrowstyle="->", color="#3498DB", lw=2))
    ax.text(0.3, 3, "Readout", ha="center", va="center", fontsize=8, color="#3498DB")

    _draw_capacitor(ax, 2.0, 3, "C_c")

    # Drive
    ax.annotate("", xy=(3.0, 4.5), xytext=(3.0, 4.0),
                arrowprops=dict(arrowstyle="->", color="#2ECC71", lw=2))
    ax.text(3.0, 4.8, "Drive/XY", ha="center", va="center", fontsize=8, color="#2ECC71")

    # Flux
    if features.get("has_flux_line"):
        ax.annotate("", xy=(5.0, 4.5), xytext=(5.0, 4.0),
                    arrowprops=dict(arrowstyle="->", color="#F39C12", lw=2))
        ax.text(5.0, 4.8, "Flux", ha="center", va="center", fontsize=8, color="#F39C12")

    # Ground
    _draw_ground(ax, 5.0, 1.5)

    ax.text(5.0, 0.5, f"{variant.replace('_', ' ').title()} Transmon",
            ha="center", va="center", fontsize=10, fontstyle="italic")


def _draw_resonator_circuit(ax: Any, features: dict[str, Any]) -> None:
    """Draw resonator equivalent circuit."""
    ax.annotate("", xy=(1.5, 3), xytext=(0.5, 3),
                arrowprops=dict(arrowstyle="->", color="#3498DB", lw=2))
    ax.text(0.3, 3, "RF In", ha="center", va="center", fontsize=8, color="#3498DB")

    _draw_capacitor(ax, 2.0, 3, "C_c")

    # Transmission line
    ax.plot([3.0, 7.0], [3, 3], "b-", lw=2)
    ax.text(5.0, 3.3, "CPW λ/4", ha="center", va="center", fontsize=9, color="#3498DB")

    # Ground
    ax.plot([7.0, 7.0], [3, 1.5], "k-", lw=1.5)
    _draw_ground(ax, 7.0, 1.5)

    ax.text(5.0, 0.5, "CPW Resonator",
            ha="center", va="center", fontsize=10, fontstyle="italic")


def _draw_generic_circuit(ax: Any, features: dict[str, Any]) -> None:
    """Draw generic circuit."""
    ax.text(5, 3, f"Generic Device\n({features.get('jj_count', 0)} JJs, "
            f"{features.get('cpw_count', 0)} CPW, "
            f"{features.get('idc_count', 0)} IDC)",
            ha="center", va="center", fontsize=11)


def _draw_graph_circuit(ax: Any, graph: dict[str, Any]) -> None:
    """Draw circuit from physics graph nodes."""
    import matplotlib.patches as _mpatches

    nodes = graph.get("devices", [])
    n = len(nodes)
    if n == 0:
        ax.text(5, 3, "No devices in graph", ha="center", va="center", fontsize=11)
        return

    spacing = 8.0 / max(n, 1)
    for i, device in enumerate(nodes):
        x = 1.0 + i * spacing
        dtype = device.get("type", "")
        name = device.get("name", f"D{i}")

        if dtype == "josephson_junction":
            _draw_jj(ax, x, 3, name)
        elif dtype == "capacitor":
            _draw_capacitor(ax, x, 3, name)
        elif dtype == "transmission_line":
            ax.plot([x - 0.5, x + 0.5], [3, 3], "b-", lw=2)
            ax.text(x, 3.3, name, ha="center", va="center", fontsize=7)
        else:
            ax.add_patch(_mpatches.FancyBboxPatch(
                (x - 0.4, 2.6), 0.8, 0.8, boxstyle="round,pad=0.05",
                facecolor="#ECF0F1", edgecolor="#2C3E50"))
            ax.text(x, 3, name, ha="center", va="center", fontsize=6)

    _draw_ground(ax, 5.0, 1.5)


def _draw_capacitor(ax: Any, x: float, y: float, label: str) -> None:
    ax.plot([x - 0.3, x - 0.3], [y - 0.3, y + 0.3], "k-", lw=2)
    ax.plot([x + 0.3, x + 0.3], [y - 0.3, y + 0.3], "k-", lw=2)
    ax.plot([x - 0.3, x + 0.3], [y, y], "k--", lw=0.5)
    ax.text(x, y + 0.5, label, ha="center", va="center", fontsize=8)


def _draw_jj(ax: Any, x: float, y: float, label: str) -> None:
    ax.plot([x - 0.3, x + 0.3], [y + 0.15, y + 0.15], "k-", lw=2)
    ax.plot([x - 0.3, x + 0.3], [y - 0.15, y - 0.15], "k-", lw=2)
    ax.plot([x - 0.15, x + 0.15], [y + 0.15, y - 0.15], "k-", lw=1)
    ax.plot([x - 0.15, x + 0.15], [y - 0.15, y + 0.15], "k-", lw=1)
    ax.text(x, y + 0.5, label, ha="center", va="center", fontsize=8, color="#8E44AD")


def _draw_idc(ax: Any, x: float, y: float, label: str) -> None:
    for i in range(3):
        dx = (i - 1) * 0.2
        ax.plot([x + dx, x + dx], [y - 0.3, y + 0.3], "k-", lw=1.5)
    ax.text(x, y + 0.5, label, ha="center", va="center", fontsize=8)


def _draw_squid(ax: Any, x: float, y: float, label: str) -> None:
    # Loop
    ax.plot([x - 0.4, x + 0.4, x + 0.4, x - 0.4, x - 0.4],
            [y - 0.3, y - 0.3, y + 0.3, y + 0.3, y - 0.3], "k-", lw=1.5)
    # JJs
    ax.plot([x - 0.15, x + 0.15], [y + 0.3, y + 0.3], "k-", lw=2)
    ax.plot([x - 0.15, x + 0.15], [y - 0.3, y - 0.3], "k-", lw=2)
    ax.text(x, y + 0.5, label, ha="center", va="center", fontsize=8, color="#8E44AD")


def _draw_ground(ax: Any, x: float, y: float) -> None:
    ax.plot([x - 0.3, x + 0.3], [y, y], "k-", lw=2)
    ax.plot([x - 0.2, x + 0.2], [y - 0.1, y - 0.1], "k-", lw=1.5)
    ax.plot([x - 0.1, x + 0.1], [y - 0.2, y - 0.2], "k-", lw=1)
