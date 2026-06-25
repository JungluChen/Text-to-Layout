"""Professional mask-like layout rendering from GDS files."""

from __future__ import annotations

from pathlib import Path

from text_to_gds.pcells.layer_stack import (
    MASK_STYLES,
    SUBSTRATE_COLOR,
    draw_layer_legend,
    draw_scale_bar,
    style_for_layer,
)

Layer = tuple[int, int]


def _read_gds_polygons(gds_path: Path) -> dict[Layer, list[list[tuple[float, float]]]]:
    """Read all polygons from a GDS file grouped by (layer, datatype)."""
    import klayout.db as db

    layout = db.Layout()
    layout.read(str(gds_path))
    polygons: dict[Layer, list[list[tuple[float, float]]]] = {}
    dbu = layout.dbu
    for cell_idx in layout.each_top_cell():
        cell = layout.cell(cell_idx)
        for layer_idx in layout.layer_indices():
            li = layout.get_info(layer_idx)
            key: Layer = (li.layer, li.datatype)
            for shape in cell.shapes(layer_idx).each(db.Shapes.SPolygons):
                pts = [(p.x * dbu, p.y * dbu) for p in shape.each_point_hull()]
                if pts:
                    polygons.setdefault(key, []).append(pts)
    return polygons


def _compute_bounds(
    polygons: dict[Layer, list[list[tuple[float, float]]]]
) -> tuple[float, float, float, float]:
    """Return (xmin, ymin, xmax, ymax) in um across all polygons."""
    xs: list[float] = []
    ys: list[float] = []
    for polys in polygons.values():
        for pts in polys:
            for x, y in pts:
                xs.append(x)
                ys.append(y)
    if not xs:
        return 0.0, 0.0, 100.0, 100.0
    margin = max((max(xs) - min(xs)), (max(ys) - min(ys))) * 0.05
    return min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin


def _um_to_px(
    x_um: float, y_um: float,
    bounds: tuple[float, float, float, float],
    image_size: int,
) -> tuple[int, int]:
    """Convert micron coordinates to pixel coordinates."""
    xmin, ymin, xmax, ymax = bounds
    w = xmax - xmin or 1.0
    h = ymax - ymin or 1.0
    scale = image_size / max(w, h)
    px = int((x_um - xmin) * scale)
    py = int((ymax - y_um) * scale)  # flip Y for image coords
    return px, py


def render_mask_view(
    gds_path: Path | str,
    output_path: Path | str,
    *,
    image_size: int = 1200,
    dark_field: bool = True,
) -> Path:
    """Render a full-chip mask view of a GDS file."""
    from PIL import Image, ImageDraw

    gds_path = Path(gds_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    polygons = _read_gds_polygons(gds_path)
    bounds = _compute_bounds(polygons)
    xmin, ymin, xmax, ymax = bounds
    w_um = xmax - xmin or 1.0
    h_um = ymax - ymin or 1.0
    scale = image_size / max(w_um, h_um)
    canvas_w = max(int(w_um * scale), 1)
    canvas_h = max(int(h_um * scale), 1)

    bg = SUBSTRATE_COLOR[:3] if dark_field else (240, 242, 245)
    img = Image.new("RGBA", (canvas_w, canvas_h), (*bg, 255))
    draw = ImageDraw.Draw(img)

    # Sort layers by render order
    active_layers: set[Layer] = set(polygons.keys())
    sorted_layers = sorted(active_layers, key=lambda ly: style_for_layer(ly).render_order)

    for layer_key in sorted_layers:
        style = style_for_layer(layer_key)
        if not style.visible:
            continue
        for pts_um in polygons[layer_key]:
            pts_px = [_um_to_px(x, y, bounds, image_size) for x, y in pts_um]
            if len(pts_px) >= 3:
                draw.polygon(pts_px, fill=style.fill_rgba, outline=style.outline_rgba)

    # Annotations
    scale_um_per_px = max(w_um, h_um) / image_size
    draw_scale_bar(draw, canvas_w, canvas_h, scale_um_per_px)
    draw_layer_legend(draw, canvas_w, canvas_h, active_layers)

    # Filename label in top-left
    draw.text((10, 6), gds_path.name, fill=(200, 200, 200))

    img.save(str(output_path))
    return output_path


def render_device_zoom(
    gds_path: Path | str,
    output_path: Path | str,
    *,
    center_um: tuple[float, float] | None = None,
    span_um: float = 50.0,
    image_size: int = 800,
) -> Path:
    """Render a zoomed view of a device region."""
    from PIL import Image, ImageDraw

    gds_path = Path(gds_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    polygons = _read_gds_polygons(gds_path)

    if center_um is None:
        full_bounds = _compute_bounds(polygons)
        cx = (full_bounds[0] + full_bounds[2]) / 2.0
        cy = (full_bounds[1] + full_bounds[3]) / 2.0
    else:
        cx, cy = center_um

    half = span_um / 2.0
    bounds = (cx - half, cy - half, cx + half, cy + half)

    bg = SUBSTRATE_COLOR[:3]
    img = Image.new("RGBA", (image_size, image_size), (*bg, 255))
    draw = ImageDraw.Draw(img)

    active_layers: set[Layer] = set()
    sorted_layers = sorted(polygons.keys(), key=lambda ly: style_for_layer(ly).render_order)

    for layer_key in sorted_layers:
        style = style_for_layer(layer_key)
        if not style.visible:
            continue
        for pts_um in polygons[layer_key]:
            pts_px = [_um_to_px(x, y, bounds, image_size) for x, y in pts_um]
            # Check if any point is within the viewport
            if any(0 <= px < image_size and 0 <= py < image_size for px, py in pts_px):
                active_layers.add(layer_key)
                if len(pts_px) >= 3:
                    draw.polygon(pts_px, fill=style.fill_rgba, outline=style.outline_rgba)

    scale_um_per_px = span_um / image_size
    draw_scale_bar(draw, image_size, image_size, scale_um_per_px)
    draw_layer_legend(draw, image_size, image_size, active_layers)
    draw.text((10, 6), f"{gds_path.name} (zoom)", fill=(200, 200, 200))

    img.save(str(output_path))
    return output_path


def render_layer_legend(
    output_path: Path | str,
    active_layers: set[Layer],
    *,
    image_width: int = 280,
    line_height: int = 24,
    swatch_size: int = 16,
    margin: int = 12,
) -> Path:
    """Render a standalone layer legend image."""
    from PIL import Image, ImageDraw

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = [
        style_for_layer(ly) for ly in sorted(active_layers)
        if style_for_layer(ly).visible
    ]
    if not styles:
        styles = [style_for_layer(ly) for ly in sorted(MASK_STYLES.keys()) if MASK_STYLES[ly].visible]

    img_height = max(margin * 2 + len(styles) * line_height, 40)
    bg = SUBSTRATE_COLOR[:3]
    img = Image.new("RGBA", (image_width, img_height), (*bg, 255))
    draw = ImageDraw.Draw(img)

    y = margin
    for style in styles:
        draw.rectangle(
            [margin, y, margin + swatch_size, y + swatch_size],
            fill=style.fill_rgba,
            outline=style.outline_rgba,
        )
        draw.text((margin + swatch_size + 8, y - 1), style.legend_label, fill=(200, 200, 200))
        y += line_height

    img.save(str(output_path))
    return output_path
