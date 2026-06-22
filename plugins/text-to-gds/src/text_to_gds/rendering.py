"""Pure layout-rendering and geometry-scanning helpers for the MCP server.

These functions are extracted from ``server.py`` so the server module can focus
on MCP tool registration. They take explicit paths/arguments and hold no MCP or
workspace state, which keeps them independently testable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from text_to_gds.extraction import labels_from_gds
from text_to_gds.process import DEFAULT_PROCESS


def port_to_dict(name: str, port: Any) -> dict[str, Any]:
    layer_info = getattr(port, "layer_info", None)
    if layer_info is not None:
        layer = [int(layer_info.layer), int(layer_info.datatype)]
    else:
        port_layer = getattr(port, "layer", None)
        layer = list(port_layer) if isinstance(port_layer, tuple) else port_layer
    return {
        "name": name,
        "center": [float(v) for v in getattr(port, "center", (0.0, 0.0))],
        "width": float(getattr(port, "width", 0.0)),
        "orientation": getattr(port, "orientation", None),
        "layer": layer,
        "port_type": getattr(port, "port_type", "electrical"),
    }


def component_sidecar(
    component: Any,
    gds_path: Path,
    pcell: str,
    screenshot_path: Path,
) -> dict[str, Any]:
    try:
        port_items = component.ports.items()
    except AttributeError:
        port_items = [(p.name, p) for p in component.get_ports_list()]

    bbox = component.bbox_np().tolist() if hasattr(component, "bbox_np") else None
    return {
        "schema": "text-to-gds.sidecar.v0",
        "pcell": pcell,
        "gds_path": str(gds_path),
        "screenshot_path": str(screenshot_path),
        "bbox_um": bbox,
        "ports": [port_to_dict(name, port) for name, port in port_items],
        "labels": labels_from_gds(gds_path),
        "info": dict(component.info),
        "process_stack": DEFAULT_PROCESS.to_dict(),
    }


def layer_color(layer: list[int]) -> tuple[int, int, int, int]:
    palette = {
        (3, 0): (56, 102, 214, 190),
        (4, 0): (218, 73, 86, 210),
        (5, 0): (48, 154, 103, 190),
        (6, 0): (124, 58, 237, 180),
        (7, 0): (245, 158, 11, 210),
        (8, 0): (249, 115, 22, 210),
        (10, 0): (90, 90, 90, 170),
    }
    key = (layer[0], layer[1])
    if key in palette:
        return palette[key]
    seed = (layer[0] * 97 + layer[1] * 53) % 255
    return (80 + seed % 120, 80 + (seed * 3) % 120, 80 + (seed * 7) % 120, 180)


def render_layout_screenshot(
    layout_path: Path,
    screenshot_path: Path,
    *,
    image_size: int | tuple[int, int] = 1000,
) -> None:
    import klayout.db as kdb
    from PIL import Image, ImageDraw

    layout = kdb.Layout()
    layout.read(str(layout_path))
    dbu = float(layout.dbu)

    shapes: list[
        tuple[list[tuple[float, float]], list[list[tuple[float, float]]], list[int]]
    ] = []
    top_cell = layout.top_cell()
    if top_cell is None:
        raise ValueError(f"Layout has no top cell: {layout_path}")
    for layer_index in layout.layer_indices():
        layer_info = layout.get_info(layer_index)
        layer = [int(layer_info.layer), int(layer_info.datatype)]
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
                points = [
                    (float(point.x) * dbu, float(point.y) * dbu)
                    for point in polygon.each_point_hull()
                ]
                if len(points) >= 3:
                    holes = [
                        [
                            (float(point.x) * dbu, float(point.y) * dbu)
                            for point in polygon.each_point_hole(hole_index)
                        ]
                        for hole_index in range(polygon.holes())
                    ]
                    shapes.append((points, holes, layer))
            iterator.next()

    layer_order = {
        (3, 0): 0,
        (4, 0): 1,
        (5, 0): 2,
        (7, 0): 3,
        (6, 0): 4,
        (8, 0): 5,
        (10, 0): 6,
    }
    shapes.sort(key=lambda item: layer_order.get((item[2][0], item[2][1]), 99))

    if not shapes:
        canvas = (image_size, image_size) if isinstance(image_size, int) else image_size
        image = Image.new("RGBA", canvas, (250, 251, 252, 255))
        draw = ImageDraw.Draw(image, "RGBA")
        draw.text((24, 24), f"No drawable shapes in {layout_path.name}", fill=(30, 41, 59, 255))
        image.convert("RGB").save(screenshot_path)
        return

    min_x = min(point[0] for shape, _holes, _layer in shapes for point in shape)
    min_y = min(point[1] for shape, _holes, _layer in shapes for point in shape)
    max_x = max(point[0] for shape, _holes, _layer in shapes for point in shape)
    max_y = max(point[1] for shape, _holes, _layer in shapes for point in shape)
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    if isinstance(image_size, int):
        aspect = span_x / span_y
        if aspect >= 2.0:
            canvas_width, canvas_height = int(image_size * 1.4), max(int(image_size * 0.5), 420)
        elif aspect <= 0.5:
            canvas_width, canvas_height = max(int(image_size * 0.5), 420), int(image_size * 1.4)
        else:
            canvas_width = canvas_height = image_size
    else:
        canvas_width, canvas_height = image_size
    image = Image.new("RGBA", (canvas_width, canvas_height), (250, 251, 252, 255))
    draw = ImageDraw.Draw(image, "RGBA")
    margin = max(min(canvas_width, canvas_height) * 0.08, 24.0)
    scale = min(
        (canvas_width - 2 * margin) / span_x,
        (canvas_height - 2 * margin) / span_y,
    )
    drawn_width = span_x * scale
    drawn_height = span_y * scale
    offset_x = (canvas_width - drawn_width) / 2.0
    offset_y = (canvas_height - drawn_height) / 2.0

    def to_px(x_um: float, y_um: float) -> tuple[float, float]:
        x_px = offset_x + (x_um - min_x) * scale
        y_px = offset_y + drawn_height - (y_um - min_y) * scale
        return x_px, y_px

    background = (250, 251, 252, 255)
    for polygon_um, holes_um, layer in shapes:
        points = [to_px(x, y) for x, y in polygon_um]
        fill = layer_color(layer)
        outline = (20, 31, 46, 220)
        draw.polygon(points, fill=fill, outline=outline)
        for hole_um in holes_um:
            draw.polygon([to_px(x, y) for x, y in hole_um], fill=background)

    draw.rectangle(
        (8, 8, canvas_width - 8, canvas_height - 8),
        outline=(148, 163, 184, 255),
        width=2,
    )
    draw.text((18, 18), layout_path.name, fill=(30, 41, 59, 255))
    image.convert("RGB").save(screenshot_path)


def scan_min_width_violations(
    layout_path: Path,
    min_width_um: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        import klayout.db as kdb
    except ImportError:
        return [], {
            "engine": "mock",
            "checked_shapes": 0,
            "warnings": ["KLayout Python module is unavailable; skipped geometry scan."],
        }

    layout = kdb.Layout()
    layout.read(str(layout_path))

    violations: list[dict[str, Any]] = []
    checked_shapes = 0
    dbu = float(layout.dbu)

    for layer_index in layout.layer_indices():
        layer_info = layout.get_info(layer_index)
        layer = [int(layer_info.layer), int(layer_info.datatype)]
        for cell in layout.each_cell():
            for shape in cell.shapes(layer_index).each():
                bbox = shape.bbox()
                width_um = abs(float(bbox.width()) * dbu)
                height_um = abs(float(bbox.height()) * dbu)
                if width_um <= 0.0 or height_um <= 0.0:
                    continue

                checked_shapes += 1
                min_dimension_um = min(width_um, height_um)
                if min_dimension_um < min_width_um:
                    violations.append(
                        {
                            "rule": "min_bbox_width",
                            "message": (
                                f"Shape minimum bounding-box dimension {min_dimension_um:.6g} um "
                                f"is below {min_width_um:.6g} um."
                            ),
                            "severity": "error",
                            "cell": cell.name,
                            "layer": layer,
                            "bbox_um": [
                                float(bbox.left) * dbu,
                                float(bbox.bottom) * dbu,
                                float(bbox.right) * dbu,
                                float(bbox.top) * dbu,
                            ],
                            "min_dimension_um": min_dimension_um,
                        }
                    )

    return violations, {
        "engine": "klayout_python_bbox",
        "checked_shapes": checked_shapes,
        "dbu_um": dbu,
        "warnings": [],
    }
