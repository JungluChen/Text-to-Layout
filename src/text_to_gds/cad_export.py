from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

from text_to_gds.extraction import layer_bounding_boxes_from_gds
from text_to_gds.preview import LAYER_COLORS
from text_to_gds.process import DEFAULT_PROCESS


def _layer_order() -> dict[str, int]:
    return {name: index for index, name in enumerate(DEFAULT_PROCESS.layers)}


def _bbox(boxes: list[dict[str, Any]]) -> list[float] | None:
    if not boxes:
        return None
    return [
        min(float(box["bbox_um"][0]) for box in boxes),
        min(float(box["bbox_um"][1]) for box in boxes),
        max(float(box["bbox_um"][2]) for box in boxes),
        max(float(box["bbox_um"][3]) for box in boxes),
    ]


def _layer_z_um() -> dict[str, tuple[float, float]]:
    z_um = 0.0
    stack: dict[str, tuple[float, float]] = {}
    for name, spec in DEFAULT_PROCESS.layers.items():
        thickness_um = max(float(spec.thickness_nm) / 1000.0, 0.01)
        stack[name] = (z_um, thickness_um)
        z_um += thickness_um
    return stack


def _layer_summary(boxes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for box in boxes:
        layer_name = str(box.get("layer_name", "unknown"))
        item = summary.setdefault(
            layer_name,
            {
                "layer_name": layer_name,
                "material": box.get("material", "unknown"),
                "shape_count": 0,
                "total_area_um2": 0.0,
            },
        )
        item["shape_count"] += 1
        item["total_area_um2"] += float(box.get("area_um2", 0.0))
    order = _layer_order()
    return sorted(summary.values(), key=lambda item: order.get(str(item["layer_name"]), 99))


def _scale_point(
    x_um: float,
    y_um: float,
    bbox_um: list[float],
    *,
    width: int,
    height: int,
    margin: float,
) -> tuple[float, float]:
    min_x, min_y, max_x, max_y = bbox_um
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    scale = min((width - 2 * margin) / span_x, (height - 2 * margin) / span_y)
    drawn_width = span_x * scale
    drawn_height = span_y * scale
    offset_x = (width - drawn_width) / 2.0
    offset_y = (height - drawn_height) / 2.0
    return (
        offset_x + (x_um - min_x) * scale,
        offset_y + drawn_height - (y_um - min_y) * scale,
    )


def write_layout_svg(gds_path: Path, boxes: list[dict[str, Any]], svg_path: Path) -> None:
    width = 1100
    height = 820
    margin = 70.0
    bbox_um = _bbox(boxes) or [0.0, 0.0, 1.0, 1.0]
    order = _layer_order()
    sorted_boxes = sorted(boxes, key=lambda box: order.get(str(box.get("layer_name")), 99))
    rects = []
    legend = []
    seen_layers: set[str] = set()
    for box in sorted_boxes:
        left, bottom, right, top = [float(value) for value in box["bbox_um"]]
        x0, y1 = _scale_point(left, bottom, bbox_um, width=width, height=height, margin=margin)
        x1, y0 = _scale_point(right, top, bbox_um, width=width, height=height, margin=margin)
        layer_name = str(box.get("layer_name", "unknown"))
        color = LAYER_COLORS.get(layer_name, "#64748b")
        rects.append(
            "<rect "
            f'x="{min(x0, x1):.3f}" y="{min(y0, y1):.3f}" '
            f'width="{abs(x1 - x0):.3f}" height="{abs(y1 - y0):.3f}" '
            f'fill="{color}" fill-opacity="0.64" stroke="#0f172a" stroke-width="1" '
            f'><title>{html.escape(layer_name)}</title></rect>'
        )
        if layer_name not in seen_layers:
            seen_layers.add(layer_name)
            y = 72 + len(legend) * 24
            legend.append(
                f'<rect x="900" y="{y}" width="14" height="14" fill="{color}" />'
                f'<text x="922" y="{y + 12}" font-size="13">{html.escape(layer_name)}</text>'
            )

    min_x, min_y, max_x, max_y = bbox_um
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect x="0" y="0" width="{width}" height="{height}" fill="#f8fafc" />
  <text x="42" y="42" font-size="22" font-family="Arial" fill="#0f172a">{html.escape(gds_path.name)}</text>
  <text x="42" y="66" font-size="13" font-family="Arial" fill="#475569">Units: microns. Bounds: [{min_x:.3f}, {min_y:.3f}] to [{max_x:.3f}, {max_y:.3f}]</text>
  <g font-family="Arial">{''.join(rects)}</g>
  <g font-family="Arial">{''.join(legend)}</g>
  <rect x="14" y="14" width="{width - 28}" height="{height - 28}" fill="none" stroke="#94a3b8" stroke-width="2" />
</svg>
"""
    svg_path.write_text(svg, encoding="utf-8")


def write_layout_dxf(boxes: list[dict[str, Any]], dxf_path: Path) -> None:
    lines = [
        "0",
        "SECTION",
        "2",
        "HEADER",
        "9",
        "$INSUNITS",
        "70",
        "13",
        "0",
        "ENDSEC",
        "0",
        "SECTION",
        "2",
        "ENTITIES",
    ]
    for box in boxes:
        left, bottom, right, top = [float(value) for value in box["bbox_um"]]
        layer_name = str(box.get("layer_name", "LAYOUT"))
        points = [(left, bottom), (right, bottom), (right, top), (left, top)]
        lines.extend(["0", "LWPOLYLINE", "8", layer_name, "90", "4", "70", "1"])
        for x, y in points:
            lines.extend(["10", f"{x:.9g}", "20", f"{y:.9g}"])
    lines.extend(["0", "ENDSEC", "0", "EOF"])
    dxf_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _facet(normal: tuple[float, float, float], points: list[tuple[float, float, float]]) -> str:
    nx, ny, nz = normal
    vertices = "".join(f"      vertex {x:.9g} {y:.9g} {z:.9g}\n" for x, y, z in points)
    return (
        f"  facet normal {nx:.9g} {ny:.9g} {nz:.9g}\n"
        "    outer loop\n"
        f"{vertices}"
        "    endloop\n"
        "  endfacet\n"
    )


def _box_facets(
    left: float,
    bottom: float,
    right: float,
    top: float,
    z0: float,
    z1: float,
) -> list[str]:
    p000 = (left, bottom, z0)
    p100 = (right, bottom, z0)
    p110 = (right, top, z0)
    p010 = (left, top, z0)
    p001 = (left, bottom, z1)
    p101 = (right, bottom, z1)
    p111 = (right, top, z1)
    p011 = (left, top, z1)
    quads = [
        ((0.0, 0.0, -1.0), [p000, p010, p110, p100]),
        ((0.0, 0.0, 1.0), [p001, p101, p111, p011]),
        ((0.0, -1.0, 0.0), [p000, p100, p101, p001]),
        ((1.0, 0.0, 0.0), [p100, p110, p111, p101]),
        ((0.0, 1.0, 0.0), [p110, p010, p011, p111]),
        ((-1.0, 0.0, 0.0), [p010, p000, p001, p011]),
    ]
    facets = []
    for normal, quad in quads:
        facets.append(_facet(normal, [quad[0], quad[1], quad[2]]))
        facets.append(_facet(normal, [quad[0], quad[2], quad[3]]))
    return facets


def write_stack_stl(boxes: list[dict[str, Any]], stl_path: Path) -> None:
    layer_z = _layer_z_um()
    facets = []
    for box in boxes:
        left, bottom, right, top = [float(value) for value in box["bbox_um"]]
        if math.isclose(left, right) or math.isclose(bottom, top):
            continue
        z0, thickness = layer_z.get(str(box.get("layer_name")), (0.0, 0.02))
        facets.extend(_box_facets(left, bottom, right, top, z0, z0 + thickness))
    stl_path.write_text("solid text_to_gds_stack\n" + "".join(facets) + "endsolid text_to_gds_stack\n")


def write_stack_glb(boxes: list[dict[str, Any]], glb_path: Path) -> tuple[bool, str | None]:
    try:
        import numpy as np
        import trimesh
    except ImportError as error:
        return False, str(error)

    layer_z = _layer_z_um()
    meshes = []
    for box in boxes:
        left, bottom, right, top = [float(value) for value in box["bbox_um"]]
        width = right - left
        depth = top - bottom
        if width <= 0.0 or depth <= 0.0:
            continue
        z0, thickness = layer_z.get(str(box.get("layer_name")), (0.0, 0.02))
        transform = np.eye(4)
        transform[:3, 3] = [left + width / 2.0, bottom + depth / 2.0, z0 + thickness / 2.0]
        mesh = trimesh.creation.box(extents=(width, depth, thickness), transform=transform)
        mesh.metadata["name"] = str(box.get("layer_name", "layer"))
        meshes.append(mesh)
    if not meshes:
        return False, "No positive-area boxes to export."
    scene = trimesh.Scene(meshes)
    scene.export(glb_path)
    return True, None


def write_cad_artifacts(
    gds_path: str | Path,
    *,
    svg_path: str | Path,
    dxf_path: str | Path,
    stl_path: str | Path,
    glb_path: str | Path,
    json_path: str | Path,
) -> dict[str, Any]:
    """Export CAD/interchange artifacts derived from a GDS layer-box inspection."""
    gds = Path(gds_path)
    svg = Path(svg_path)
    dxf = Path(dxf_path)
    stl = Path(stl_path)
    glb = Path(glb_path)
    report_path = Path(json_path)
    for path in (svg, dxf, stl, glb, report_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    boxes = layer_bounding_boxes_from_gds(gds)
    order = _layer_order()
    boxes.sort(key=lambda box: order.get(str(box.get("layer_name")), 99))

    warnings: list[str] = []
    write_layout_svg(gds, boxes, svg)
    write_layout_dxf(boxes, dxf)
    write_stack_stl(boxes, stl)
    glb_ok, glb_warning = write_stack_glb(boxes, glb)
    if glb_warning:
        warnings.append(f"GLB export: {glb_warning}")

    outputs = {
        "layout_svg": str(svg),
        "layout_dxf": str(dxf),
        "stack_stl": str(stl),
        "stack_glb": str(glb) if glb_ok else None,
    }
    report = {
        "schema": "text-to-gds.cad-export.v0",
        "source_gds": str(gds),
        "units": "microns",
        "coordinate_system": "XY layout plane, +Z process stack thickness",
        "shape_count": len(boxes),
        "bbox_um": _bbox(boxes),
        "layers": _layer_summary(boxes),
        "outputs": outputs,
        "warnings": warnings,
        "model_validity": (
            "CAD exports are inspection/interchange artifacts derived from GDS bounding boxes; "
            "they are not mask signoff, EM extraction, or a STEP mechanical source of truth."
        ),
        "report_path": str(report_path),
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
