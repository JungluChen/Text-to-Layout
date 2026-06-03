from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from text_to_gds.extraction import layer_bounding_boxes_from_gds

LAYER_COLORS = {
    "M1": "#3866d6",
    "JJ": "#da4956",
    "M2": "#309a67",
    "M3": "#7c3aed",
    "VIA12": "#f59e0b",
    "VIA23": "#f97316",
    "MARKER": "#64748b",
}


def _scale_boxes(boxes: list[dict[str, Any]], image_width: int, image_height: int) -> list[dict[str, Any]]:
    if not boxes:
        return []
    min_x = min(box["bbox_um"][0] for box in boxes)
    min_y = min(box["bbox_um"][1] for box in boxes)
    max_x = max(box["bbox_um"][2] for box in boxes)
    max_y = max(box["bbox_um"][3] for box in boxes)
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    margin = 48.0
    scale = min((image_width - 2 * margin) / span_x, (image_height - 2 * margin) / span_y)

    scaled = []
    for box in boxes:
        left, bottom, right, top = box["bbox_um"]
        layer_offset = len(scaled) * 0.0
        scaled.append(
            {
                **box,
                "x": margin + (left - min_x) * scale + layer_offset,
                "y": image_height - (margin + (top - min_y) * scale) + layer_offset,
                "width": max((right - left) * scale, 1.0),
                "height": max((top - bottom) * scale, 1.0),
            }
        )
    return scaled


def write_stack_preview(
    gds_path: str | Path,
    html_path: str | Path,
    json_path: str | Path,
) -> dict[str, Any]:
    """Write a local 2.5D process-stack preview from GDS layer bounding boxes."""
    gds_path = Path(gds_path)
    html_path = Path(html_path)
    json_path = Path(json_path)
    boxes = layer_bounding_boxes_from_gds(gds_path)
    layer_order = {name: index for index, name in enumerate(["M1", "JJ", "M2", "VIA12", "M3", "VIA23", "MARKER"])}
    boxes.sort(key=lambda box: layer_order.get(str(box["layer_name"]), 99))

    preview = {
        "schema": "text-to-gds.stack-preview.v0",
        "gds_path": str(gds_path),
        "shape_count": len(boxes),
        "layers": boxes,
    }
    json_path.write_text(json.dumps(preview, indent=2), encoding="utf-8")

    width = 980
    height = 640
    scaled = _scale_boxes(boxes, width, height)
    rects = []
    legend_items = []
    seen_layers = set()
    for index, box in enumerate(scaled):
        z_offset = layer_order.get(str(box["layer_name"]), index) * 10
        color = LAYER_COLORS.get(str(box["layer_name"]), "#64748b")
        label = html.escape(f'{box["layer_name"]} {box["material"]} {box["thickness_nm"]} nm')
        rects.append(
            f'<rect x="{box["x"] + z_offset:.2f}" y="{box["y"] - z_offset:.2f}" '
            f'width="{box["width"]:.2f}" height="{box["height"]:.2f}" rx="1" '
            f'fill="{color}" fill-opacity="0.62" stroke="#0f172a" stroke-width="1">'
            f"<title>{label}</title></rect>"
        )
        layer_name = str(box["layer_name"])
        if layer_name not in seen_layers:
            seen_layers.add(layer_name)
            legend_items.append(
                f'<span><i style="background:{color}"></i>{html.escape(layer_name)} '
                f'{html.escape(str(box["material"]))}</span>'
            )

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Text-to-GDS Stack Preview</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, sans-serif; }}
    body {{ margin: 0; background: #f8fafc; color: #0f172a; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 24px; }}
    h1 {{ font-size: 24px; margin: 0 0 6px; }}
    p {{ margin: 0 0 18px; color: #475569; }}
    svg {{ width: 100%; height: auto; background: white; border: 1px solid #cbd5e1; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 14px; }}
    .legend span {{ display: inline-flex; align-items: center; gap: 6px; font-size: 13px; }}
    .legend i {{ width: 14px; height: 14px; border: 1px solid #0f172a; display: inline-block; }}
  </style>
</head>
<body>
  <main>
    <h1>Text-to-GDS Stack Preview</h1>
    <p>{html.escape(gds_path.name)} - {len(boxes)} extracted layer boxes</p>
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="2.5D process stack preview">
      <g transform="skewY(-10) rotate(0)">
        {''.join(rects)}
      </g>
    </svg>
    <div class="legend">{''.join(legend_items)}</div>
  </main>
</body>
</html>
"""
    html_path.write_text(html_doc, encoding="utf-8")
    return {
        "status": "previewed",
        "html_path": str(html_path),
        "json_path": str(json_path),
        "shape_count": len(boxes),
    }
