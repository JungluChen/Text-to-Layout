"""LVS graph and report generation from GDS connectivity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from textlayout._legacy.geometry.extraction import extract_layer_features
from textlayout._legacy.verification.connectivity import extract_connectivity
from textlayout._legacy.verification.drc import run_drc


def _draw_graph(connectivity: dict[str, Any], path: Path) -> None:
    nodes = connectivity["nodes"]
    edges = connectivity["edges"]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.axis("off")
    if not nodes:
        fig.savefig(path, dpi=180)
        plt.close(fig)
        return
    positions = {}
    for index, node in enumerate(nodes):
        x = (index % 6) / 5.0 if len(nodes) > 1 else 0.5
        y = 1.0 - (index // 6 + 0.5) / max((len(nodes) + 5) // 6, 1)
        positions[node["id"]] = (x, y)
        color = "#f0c84b" if node["layer"] == "JJ" else "#52b7d8"
        if node["id"] in connectivity.get("floating_nodes", []):
            color = "#d84b4b"
        ax.scatter([x], [y], s=520, color=color, edgecolors="#222")
        ax.text(x, y, node["id"], ha="center", va="center", fontsize=7)
    for edge in edges:
        if edge["source"] not in positions or edge["target"] not in positions:
            continue
        x1, y1 = positions[edge["source"]]
        x2, y2 = positions[edge["target"]]
        color = "#7c4bd8" if edge["kind"] == "jj_overlap" else "#666"
        ax.plot([x1, x2], [y1, y2], color=color, linewidth=1.2)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _sym_capacitor(ax, x: float, y: float, *, horizontal: bool = False, scale: float = 1.0) -> None:
    """Standard capacitor symbol --||-- centered at (x, y)."""
    g = 0.018 * scale
    plate = 0.05 * scale
    if horizontal:
        ax.plot([x - g, x - g], [y - plate, y + plate], color="#222", lw=2)
        ax.plot([x + g, x + g], [y - plate, y + plate], color="#222", lw=2)
    else:
        ax.plot([x - plate, x + plate], [y + g, y + g], color="#222", lw=2)
        ax.plot([x - plate, x + plate], [y - g, y - g], color="#222", lw=2)


def _sym_junction(ax, x: float, y: float, *, scale: float = 1.0) -> None:
    """Josephson junction symbol --[X]-- centered at (x, y)."""
    s = 0.05 * scale
    ax.add_patch(plt.Rectangle((x - s, y - s), 2 * s, 2 * s, fill=False, edgecolor="#b38300", lw=1.8))
    ax.plot([x - s, x + s], [y - s, y + s], color="#b38300", lw=1.8)
    ax.plot([x - s, x + s], [y + s, y - s], color="#b38300", lw=1.8)


def _draw_schematic(connectivity: dict[str, Any], path: Path) -> None:
    topo = connectivity.get("device_topology", {})
    squid_count = topo.get("squid_count", 0)
    junction_count = topo.get("junction_count", 0)
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    gnd = "#2f6fd0"
    sig = "#d8453b"

    def ground_rail(y: float = 0.12) -> None:
        ax.plot([0.1, 0.9], [y, y], color=gnd, lw=2.5)
        for i in range(5):
            gx = 0.42 + i * 0.04
            ax.plot([gx, gx + 0.03], [y - 0.02 - i * 0.0, y - 0.02], color=gnd, lw=1)
        ax.text(0.9, y - 0.03, "GND", color=gnd, fontsize=9, ha="left")

    if squid_count >= 2:
        # ---- Lumped JPA equivalent circuit -----------------------------------
        ax.text(0.5, 0.93, "Extracted JPA equivalent circuit", ha="center", fontsize=11, weight="bold")
        ax.plot([0.06, 0.30], [0.7, 0.7], color=sig, lw=2)
        ax.text(0.06, 0.74, "RF in", color=sig, fontsize=9)
        _sym_capacitor(ax, 0.30, 0.7, horizontal=True, scale=1.2)
        ax.text(0.30, 0.80, "Cc", ha="center", fontsize=9)
        ax.plot([0.32, 0.62], [0.7, 0.7], color=sig, lw=2)
        node_x = 0.62
        ax.scatter([node_x], [0.7], s=30, color="#111", zorder=5)
        ax.text(node_x + 0.01, 0.74, "LC node", fontsize=9)
        # IDC shunt branch
        ax.plot([node_x, node_x], [0.7, 0.5], color="#222", lw=1.5)
        _sym_capacitor(ax, node_x, 0.42, scale=1.4)
        ax.text(node_x + 0.06, 0.42, "C (IDC)", fontsize=9)
        ax.plot([node_x, node_x], [0.34, 0.12], color="#222", lw=1.5)
        # SQUID array branch
        arr_x = 0.80
        ax.plot([node_x, arr_x], [0.7, 0.7], color="#222", lw=1.5)
        ax.plot([arr_x, arr_x], [0.7, 0.58], color="#222", lw=1.5)
        shown = min(squid_count, 3)
        step = (0.58 - 0.16) / shown
        for i in range(shown):
            yc = 0.58 - (i + 0.5) * step
            _sym_junction(ax, arr_x - 0.03, yc, scale=0.7)
            _sym_junction(ax, arr_x + 0.03, yc, scale=0.7)
            ax.plot([arr_x - 0.06, arr_x - 0.06], [yc + 0.035, yc - 0.035], color="#222", lw=1)
            ax.plot([arr_x + 0.06, arr_x + 0.06], [yc + 0.035, yc - 0.035], color="#222", lw=1)
        ax.text(arr_x + 0.08, 0.4, f"SQUID x{squid_count}", fontsize=9, color="#b38300")
        ax.plot([arr_x, arr_x], [0.16, 0.12], color="#222", lw=1.5)
        ground_rail()
    elif squid_count == 1:
        # ---- Transmon equivalent circuit -------------------------------------
        ax.text(0.5, 0.93, "Extracted transmon equivalent circuit", ha="center", fontsize=11, weight="bold")
        top_y, bot_y = 0.66, 0.30
        ax.plot([0.30, 0.70], [top_y, top_y], color="#2e8b57", lw=3)
        ax.plot([0.30, 0.70], [bot_y, bot_y], color="#2e8b57", lw=3)
        ax.text(0.72, top_y, "island A", color="#2e8b57", fontsize=9)
        ax.text(0.72, bot_y, "island B", color="#2e8b57", fontsize=9)
        # SQUID (two parallel junctions) between islands
        for jx in (0.42, 0.58):
            ax.plot([jx, jx], [top_y, 0.54], color="#222", lw=1.4)
            _sym_junction(ax, jx, 0.48, scale=0.8)
            ax.plot([jx, jx], [0.42, bot_y], color="#222", lw=1.4)
        ax.text(0.5, 0.49, "SQUID", ha="center", fontsize=8, color="#b38300")
        # shunt capacitor (the two islands)
        ax.plot([0.34, 0.34], [top_y, bot_y], color="#222", lw=1.4)
        _sym_capacitor(ax, 0.34, 0.48, scale=1.0)
        ax.text(0.20, 0.48, "C_shunt", fontsize=9)
        # readout coupling
        ax.plot([0.70, 0.84], [top_y, top_y], color="#222", lw=1.2)
        _sym_capacitor(ax, 0.84, top_y, horizontal=True, scale=0.9)
        ax.text(0.84, top_y + 0.06, "Cc", ha="center", fontsize=8)
        ax.plot([0.86, 0.93], [top_y, top_y], color=sig, lw=2)
        ax.text(0.88, top_y - 0.05, "readout", color=sig, fontsize=8)
    else:
        ax.text(0.5, 0.6, "No junction topology extracted", ha="center", fontsize=11)

    status = connectivity.get("status", "unknown")
    color = {"passed": "#2d6a4f", "warning": "#9d4d00", "failed": "#b00020"}.get(status, "#444")
    ax.text(
        0.5,
        0.03,
        f"geometry-extracted: {junction_count} junction(s), {squid_count} SQUID(s)   |   LVS: {status}",
        ha="center",
        fontsize=9,
        color=color,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _draw_overlay(connectivity: dict[str, Any], path: Path) -> None:
    nodes = connectivity["nodes"]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    if not nodes:
        fig.savefig(path, dpi=180)
        plt.close(fig)
        return
    colors = {
        "M1": "#3f7fd0",
        "M2": "#34a853",
        "M3": "#7e4bd8",
        "JJ": "#f0c84b",
        "VIA12": "#80deea",
        "VIA23": "#80deea",
    }
    for node in nodes:
        x1, y1, x2, y2 = node["bbox"]
        color = "#d84b4b" if node["id"] in connectivity.get("floating_nodes", []) else colors.get(node["layer"], "#999")
        ax.add_patch(
            plt.Rectangle(
                (x1, y1),
                max(x2 - x1, 1),
                max(y2 - y1, 1),
                facecolor=color,
                edgecolor="#111",
                linewidth=0.4,
                alpha=0.65,
            )
        )
        ax.text((x1 + x2) / 2.0, (y1 + y2) / 2.0, node["id"], fontsize=6, ha="center", va="center")
    all_x = [coord for node in nodes for coord in (node["bbox"][0], node["bbox"][2])]
    all_y = [coord for node in nodes for coord in (node["bbox"][1], node["bbox"][3])]
    margin_x = max((max(all_x) - min(all_x)) * 0.05, 10)
    margin_y = max((max(all_y) - min(all_y)) * 0.05, 10)
    ax.set_xlim(min(all_x) - margin_x, max(all_x) + margin_x)
    ax.set_ylim(min(all_y) - margin_y, max(all_y) + margin_y)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def generate_lvs_report(gds_path: str | Path, output_dir: str | Path, stem: str) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    graph_path = out / f"{stem}.lvs_graph.png"
    overlay_path = out / f"{stem}.net_overlay.png"
    schematic_path = out / f"{stem}.schematic.png"
    report_path = out / f"{stem}.lvs.json"
    connectivity = extract_connectivity(gds_path)
    _draw_graph(connectivity, graph_path)
    _draw_overlay(connectivity, overlay_path)
    _draw_schematic(connectivity, schematic_path)
    report = {
        "schema": "text-to-gds.lvs-report.v1",
        "gds_path": str(gds_path),
        "geometry": extract_layer_features(gds_path),
        "connectivity": connectivity,
        "drc": run_drc(gds_path),
        "graph_path": str(graph_path),
        "overlay_path": str(overlay_path),
        "schematic_path": str(schematic_path),
        "status": connectivity["status"],
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report
