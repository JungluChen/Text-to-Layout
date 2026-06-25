"""Production-grade four-view device figures.

For each device this module renders four *separate* clean figures:

  * ``<stem>.mask_view.png``    — single-tone GDS mask (blueprint look)
  * ``<stem>.layer_view.png``   — layer-coloured view, legend off the device
  * ``<stem>.net_view.png``     — extracted electrical nets, role-coloured, ports outside
  * ``<stem>.circuit_view.png`` — standard equivalent-circuit symbols

Design rules enforced here: labels do not overlap, ports are drawn *outside* the
geometry with leader lines, the scale bar is a rounded readable length, and the
legend never covers the device (it lives in a reserved right-hand margin).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import PathPatch  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402

import klayout.db as kdb  # noqa: E402

from text_to_gds.geometry.polygon import load_layout  # noqa: E402
from text_to_gds.pdk.layers import layer_name  # noqa: E402
from text_to_gds.verification.lvs import _draw_schematic  # noqa: E402

_DARK = "#0e1116"
_INK = "#16213e"
_LIGHT = "#f6f7f9"

_CONDUCTOR = ("M1", "M2", "M3", "VIA12", "VIA23")

LAYER_STYLE: dict[str, tuple[str, str]] = {
    "M1": ("#3f7fd0", "M1 — ground / bottom electrode"),
    "M2": ("#34a853", "M2 — top electrode / CPW"),
    "M3": ("#9a6ce0", "M3 — wiring / flux"),
    "JJ": ("#f0c84b", "JJ — Josephson junction"),
    "VIA12": ("#ff8a3d", "VIA12 — M1↔M2"),
    "VIA23": ("#ff5d3d", "VIA23 — M2↔M3"),
    "MARKER": ("#9aa4b2", "boundary / airbridge / wirebond"),
}

# Net-role palette (matches the spec: red=RF, blue=ground, yellow=JJ,
# green=floating island, purple=flux).
ROLE_STYLE = {
    "rf": ("#e0453b", "RF signal"),
    "ground": ("#2f6fd0", "ground"),
    "jj": ("#f0c84b", "Josephson junction"),
    "island": ("#2e9e57", "floating island / LC node"),
    "flux": ("#9a4bd8", "flux bias"),
}


def _layer_polys(path: str | Path) -> tuple[dict[str, list[tuple[list, list]]], float]:
    """Return {layer_name: [(hull_um, [hole_um, ...]), ...]} plus the layout dbu."""
    layout, top = load_layout(path)
    dbu = layout.dbu
    out: dict[str, list[tuple[list, list]]] = {}
    for layer_index in layout.layer_indexes():
        info = layout.get_info(layer_index)
        name = layer_name((info.layer, info.datatype))
        region = kdb.Region()
        shape_iter = top.begin_shapes_rec(layer_index)
        while not shape_iter.at_end():
            shape = shape_iter.shape()
            poly = None
            if shape.is_box():
                poly = kdb.Polygon(shape.box)
            elif shape.is_path():
                poly = shape.path.polygon()
            elif shape.is_polygon() or shape.is_simple_polygon():
                poly = shape.polygon
            if poly is not None:
                region.insert(poly.transformed(shape_iter.trans()))
            shape_iter.next()
        region.merge()
        if region.is_empty():
            continue
        polys: list[tuple[list, list]] = []
        for poly in region.each_merged():
            hull = [(pt.x * dbu, pt.y * dbu) for pt in poly.each_point_hull()]
            holes = [
                [(pt.x * dbu, pt.y * dbu) for pt in poly.each_point_hole(h)]
                for h in range(poly.holes())
            ]
            polys.append((hull, holes))
        out[name] = polys
    return out, dbu


def _mpl_path(hull: list, holes: list) -> MplPath:
    verts = list(hull) + [hull[0]]
    codes = [MplPath.MOVETO] + [MplPath.LINETO] * (len(hull) - 1) + [MplPath.CLOSEPOLY]
    for hole in holes:
        verts += list(hole) + [hole[0]]
        codes += [MplPath.MOVETO] + [MplPath.LINETO] * (len(hole) - 1) + [MplPath.CLOSEPOLY]
    return MplPath(verts, codes)


def _bounds(polys: dict[str, list[tuple[list, list]]]) -> tuple[float, float, float, float]:
    xs, ys = [], []
    for parts in polys.values():
        for hull, _holes in parts:
            for x, y in hull:
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def _nice(value: float) -> float:
    if value <= 0:
        return 1.0
    exp = math.floor(math.log10(value))
    frac = value / (10.0**exp)
    nice = 1.0 if frac < 1.5 else 2.0 if frac < 3.5 else 5.0 if frac < 7.5 else 10.0
    return nice * (10.0**exp)


def _setup_axes(ax, bounds, *, dark: bool) -> None:
    minx, miny, maxx, maxy = bounds
    spanx, spany = maxx - minx, maxy - miny
    mx, my = spanx * 0.16 + 10.0, spany * 0.16 + 10.0
    ax.set_xlim(minx - mx, maxx + mx)
    ax.set_ylim(miny - my, maxy + my)
    ax.set_aspect("equal")
    ax.axis("off")
    if dark:
        ax.set_facecolor(_DARK)


def _scale_bar(ax, bounds, *, dark: bool) -> None:
    minx, miny, maxx, maxy = bounds
    spanx = maxx - minx
    length = _nice(spanx * 0.22)
    x0 = minx
    y0 = miny - (maxy - miny) * 0.10
    color = "#e8eaed" if dark else "#222"
    ax.plot([x0, x0 + length], [y0, y0], color=color, lw=3, solid_capstyle="butt")
    label = f"{length:.0f} µm" if length >= 1 else f"{length:.2f} µm"
    ax.text(x0 + length / 2.0, y0 - (maxy - miny) * 0.04, label, ha="center", va="top",
            fontsize=9, color=color)


def _draw_polys(ax, parts, *, facecolor, edgecolor, alpha=1.0, lw=0.6, fill=True):
    for hull, holes in parts:
        patch = PathPatch(
            _mpl_path(hull, holes),
            facecolor=facecolor if fill else "none",
            edgecolor=edgecolor,
            lw=lw,
            alpha=alpha,
        )
        ax.add_patch(patch)


def _title(ax, text: str, *, dark: bool) -> None:
    color = "#e8eaed" if dark else "#1a1a1a"
    ax.set_title(text, color=color, fontsize=12, weight="bold", pad=12)


# --------------------------------------------------------------------------- #
# 1. mask view
# --------------------------------------------------------------------------- #
def render_mask_view(polys, bounds, path: Path, title: str) -> None:
    """Signoff mask: true polarity (opaque metal = drawn), no decorative colours."""
    fig, ax = plt.subplots(figsize=(7.4, 6.0))
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")
    _setup_axes(ax, bounds, dark=False)
    # All superconductor layers are the same opaque tone (metal kept = black);
    # ground-plane pockets are real holes and render as white (no metal).
    for name in _CONDUCTOR:
        if name in polys:
            _draw_polys(ax, polys[name], facecolor="#000000", edgecolor="#000000", lw=0.2)
    if "JJ" in polys:
        # Junctions are a distinct process layer; shown as a dark hatch tone.
        _draw_polys(ax, polys["JJ"], facecolor="#444444", edgecolor="#000000", lw=0.3)
    if "MARKER" in polys:  # chip boundary / placeholders: outline only (not a metal mask)
        _draw_polys(ax, polys["MARKER"], facecolor="none", edgecolor="#888888", lw=0.6, fill=False)
    _scale_bar(ax, bounds, dark=False)
    _title(ax, f"{title} — signoff mask", dark=False)
    ax.text(0.5, -0.02, "true mask polarity: opaque = superconductor, white = etched/substrate",
            transform=ax.transAxes, ha="center", va="top", fontsize=8, color="#555")
    fig.savefig(path, dpi=190, bbox_inches="tight", facecolor="#ffffff")
    plt.close(fig)


def render_evidence_view(bundle: dict[str, Any], path: str | Path, title: str) -> None:
    """Tabular provenance view: every reported value + its solver evidence + source."""
    items = bundle.get("evidence", [])
    headers = ["quantity", "solver", "status", "value", "unit", "source", "out file", "freq GHz"]
    status_color = {"EXECUTED": "#2e7d32", "PREPARED": "#1565c0", "SKIPPED": "#9d6000", "FAILED": "#b00020"}
    rows = []
    cell_colors = []
    for it in items:
        val = it.get("value")
        if isinstance(val, float):
            vtxt = f"{val:.4g}"
        elif val is None:
            vtxt = "—"
        else:
            vtxt = str(val)
        band = it.get("frequency_range_ghz")
        band_txt = f"{band[0]:.2f}-{band[1]:.2f}" if band else "—"
        out_txt = "yes" if it.get("output_file_exists") else "no"
        # Source/provenance: show the notes field which explains where the value came from
        source_txt = it.get("notes") or "—"
        if len(source_txt) > 60:
            source_txt = source_txt[:57] + "..."
        rows.append([
            it["quantity"], it["solver_name"], it["solver_status"], vtxt,
            it.get("unit") or "—", source_txt, out_txt, band_txt,
        ])
        sc = status_color.get(it["solver_status"], "#333")
        cell_colors.append(["#ffffff", "#ffffff", sc, "#ffffff", "#ffffff", "#ffffff", "#ffffff", "#ffffff"])

    fig_h = 1.6 + 0.42 * max(len(rows), 1)
    fig, ax = plt.subplots(figsize=(13.0, fig_h))
    ax.axis("off")
    ax.set_title(f"{title} — solver evidence (provenance)", fontsize=13, weight="bold", pad=14)
    if rows:
        table = ax.table(cellText=rows, colLabels=headers, cellColours=cell_colors,
                         cellLoc="left", loc="center")
        table.auto_set_font_size(False)
        table.set_fontsize(8.0)
        table.scale(1.0, 1.5)
        for (r, _c), cell in table.get_celld().items():
            if r == 0:
                cell.set_facecolor("#222b3a")
                cell.set_text_props(color="#ffffff", weight="bold")
            elif cell.get_facecolor()[:3] != (1.0, 1.0, 1.0):
                cell.set_text_props(color="#ffffff", weight="bold")
    executed = bundle.get("executed_quantities", [])
    skipped = bundle.get("skipped_quantities", [])
    note = (
        f"EXECUTED: {len(executed)} quantity(ies) have output file on disk.  "
        f"SKIPPED/FAILED: {len(skipped)} item(s) — each names the missing solver/backend."
    )
    ax.text(0.5, -0.04, note, transform=ax.transAxes, ha="center", va="top", fontsize=8.5, color="#444")
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="#ffffff")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# 2. layer view
# --------------------------------------------------------------------------- #
def render_layer_view(polys, bounds, path: Path, title: str, ports, annotations) -> None:
    fig, ax = plt.subplots(figsize=(8.6, 6.0))
    fig.patch.set_facecolor(_DARK)
    _setup_axes(ax, bounds, dark=True)
    order = ["M1", "MARKER", "M2", "M3", "VIA12", "VIA23", "JJ"]
    handles = []
    for name in order:
        if name not in polys:
            continue
        color, label = LAYER_STYLE.get(name, ("#999", name))
        fill = name != "MARKER"
        _draw_polys(ax, polys[name], facecolor=color, edgecolor=color,
                    alpha=0.85 if fill else 1.0, lw=0.6 if fill else 1.0, fill=fill)
        handles.append(plt.Line2D([0], [0], marker="s", color="none",
                                  markerfacecolor=color, markersize=10, label=label))
    _draw_ports(ax, ports, bounds, dark=True)
    _annotate(ax, annotations, bounds)
    _scale_bar(ax, bounds, dark=True)
    _title(ax, f"{title} — layer view", dark=True)
    leg = ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1.0),
                    fontsize=8, framealpha=0.0, labelcolor="#e8eaed")
    leg.set_title("layers", prop={"size": 9})
    plt.setp(leg.get_title(), color="#e8eaed")
    fig.savefig(path, dpi=190, bbox_inches="tight", facecolor=_DARK)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# 3. net view
# --------------------------------------------------------------------------- #
def _in_bbox(hull, pt, tol: float = 3.0) -> bool:
    xs = [p[0] for p in hull]
    ys = [p[1] for p in hull]
    return min(xs) - tol <= pt[0] <= max(xs) + tol and min(ys) - tol <= pt[1] <= max(ys) + tol


def _role_for(layer: str, hull, holes, ports, is_ground: bool) -> str:
    if layer == "JJ":
        return "jj"
    # A port only belongs to a polygon on the *same* layer (an M3 flux line
    # running over the M1 ground must not recolour the ground). Same-layer
    # polygons never overlap, so a layer-filtered bbox test is unambiguous and
    # also tolerant of ports placed on a polygon edge (e.g. launch-pad tips).
    for name, port in ports.items():
        if layer_name(tuple(port.layer)) != layer:
            continue
        if _in_bbox(hull, tuple(port.center_um)):
            kind = getattr(port, "kind", "")
            if name == "flux":
                return "flux"
            if kind == "rf" or name in {"signal", "pump", "readout_in", "readout_out", "drive"}:
                return "rf"
            if name == "ground":
                return "ground"
    if is_ground or layer == "M1":
        return "ground"
    if layer == "M3":
        return "flux"
    return "island"


def render_net_view(polys, bounds, connectivity, ports, path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(8.6, 6.0))
    fig.patch.set_facecolor(_DARK)
    _setup_axes(ax, bounds, dark=True)

    # identify the dominant ground polygon (largest M1 by area)
    ground_id = None
    best = -1.0
    for idx, (hull, _holes) in enumerate(polys.get("M1", [])):
        xs = [p[0] for p in hull]
        ys = [p[1] for p in hull]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if area > best:
            best = area
            ground_id = idx

    used_roles: set[str] = set()
    for layer in ("M1", "M2", "M3", "JJ"):
        for idx, (hull, holes) in enumerate(polys.get(layer, [])):
            is_ground = layer == "M1" and idx == ground_id
            role = _role_for(layer, hull, holes, ports, is_ground)
            color = ROLE_STYLE[role][0]
            used_roles.add(role)
            ax.add_patch(PathPatch(_mpl_path(hull, holes), facecolor=color,
                                   edgecolor="#0b0d12", lw=0.5, alpha=0.9))

    _draw_ports(ax, ports, bounds, dark=True)
    _scale_bar(ax, bounds, dark=True)
    _title(ax, f"{title} — extracted nets", dark=True)
    topo = connectivity.get("device_topology", {})
    ax.text(
        0.5, -0.07,
        f"geometry-extracted: {topo.get('junction_count', 0)} junction(s), "
        f"{topo.get('squid_count', 0)} SQUID(s)   |   LVS: {connectivity.get('status', '?')}",
        transform=ax.transAxes, ha="center", va="top", fontsize=8, color="#9aa4b2",
    )
    handles = [
        plt.Line2D([0], [0], marker="s", color="none", markerfacecolor=ROLE_STYLE[r][0],
                   markersize=10, label=ROLE_STYLE[r][1])
        for r in ("rf", "island", "flux", "ground", "jj")
        if r in used_roles
    ]
    leg = ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1.0),
                    fontsize=8, framealpha=0.0, labelcolor="#e8eaed")
    leg.set_title("net role", prop={"size": 9})
    plt.setp(leg.get_title(), color="#e8eaed")
    fig.savefig(path, dpi=190, bbox_inches="tight", facecolor=_DARK)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# ports + annotations (shared)
# --------------------------------------------------------------------------- #
def _draw_ports(ax, ports, bounds, *, dark: bool) -> None:
    if not ports:
        return
    minx, miny, maxx, maxy = bounds
    spanx, spany = maxx - minx, maxy - miny
    off_x, off_y = spanx * 0.12 + 8.0, spany * 0.12 + 8.0
    sides: dict[int, list] = {0: [], 90: [], 180: [], 270: []}
    for name, port in ports.items():
        o = int(round(port.orientation_deg / 90.0)) % 4 * 90
        sides[o].append((name, port))
    txt_color = "#e8eaed" if dark else "#1a1a1a"
    for o, items in sides.items():
        n = len(items)
        for i, (name, port) in enumerate(items):
            x, y = port.center_um
            frac = (i + 1) / (n + 1)
            if o == 0:
                lx, ly, ha = maxx + off_x, miny + frac * spany, "left"
            elif o == 180:
                lx, ly, ha = minx - off_x, miny + frac * spany, "right"
            elif o == 90:
                lx, ly, ha = minx + frac * spanx, maxy + off_y, "center"
            else:
                lx, ly, ha = minx + frac * spanx, miny - off_y, "center"
            ax.annotate(
                name,
                xy=(x, y),
                xytext=(lx, ly),
                ha=ha,
                va="center",
                fontsize=8,
                color=txt_color,
                arrowprops=dict(arrowstyle="->", color="#7f8896", lw=1.0,
                                shrinkA=0, shrinkB=2),
            )


def _annotate(ax, annotations, bounds) -> None:
    if not annotations:
        return
    minx, miny, maxx, maxy = bounds
    for i, (text, xy) in enumerate(annotations.items()):
        x, y = xy
        ax.annotate(
            text,
            xy=(x, y),
            xytext=(x, y),
            fontsize=7.5,
            color="#ffd479",
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.2", fc="#1b2233", ec="#ffd479", lw=0.6, alpha=0.85),
        )


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #
def render_device_views(
    gds_path: str | Path,
    out_dir: str | Path,
    stem: str,
    *,
    connectivity: dict[str, Any],
    ports: dict[str, Any],
    title: str,
    annotations: dict[str, tuple[float, float]] | None = None,
) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    polys, _dbu = _layer_polys(gds_path)
    bounds = _bounds(polys)
    paths = {
        "mask_view": out / f"{stem}.mask_view.png",
        "layer_view": out / f"{stem}.layer_view.png",
        "net_view": out / f"{stem}.net_view.png",
        "circuit_view": out / f"{stem}.circuit_view.png",
    }
    render_mask_view(polys, bounds, paths["mask_view"], title)
    render_layer_view(polys, bounds, paths["layer_view"], title, ports, annotations or {})
    render_net_view(polys, bounds, connectivity, ports, paths["net_view"], title)
    _draw_schematic(connectivity, paths["circuit_view"])
    return {k: str(v) for k, v in paths.items()}
