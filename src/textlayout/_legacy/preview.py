from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from textlayout._legacy.extraction import layer_bounding_boxes_from_gds

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
    blocks = []
    legend_items = []
    seen_layers = set()
    for index, box in enumerate(scaled):
        z_offset = layer_order.get(str(box["layer_name"]), index) * 18
        z_height = max(float(box.get("thickness_nm", 100.0)) / 35.0, 4.0)
        color = LAYER_COLORS.get(str(box["layer_name"]), "#64748b")
        label = html.escape(f'{box["layer_name"]} {box["material"]} {box["thickness_nm"]} nm')
        blocks.append(
            f'<div class="block" title="{label}" style="--x:{box["x"]:.2f}; '
            f'--y:{box["y"]:.2f}; --w:{box["width"]:.2f}; --h:{box["height"]:.2f}; '
            f'--z:{z_offset:.2f}; --t:{z_height:.2f}; --c:{color};"></div>'
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
    :root {{ color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", sans-serif; }}
    body {{ margin: 0; background: #f5f5f7; color: #1d1d1f; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 24px; }}
    h1 {{ font-size: 24px; margin: 0 0 6px; letter-spacing: 0; }}
    p {{ margin: 0 0 18px; color: #6e6e73; }}
    .viewer {{
      border: 1px solid rgba(0,0,0,0.12);
      border-radius: 24px;
      background: linear-gradient(180deg, #fff, #fbfbfd);
      overflow: hidden;
      box-shadow: 0 24px 70px rgba(0,0,0,0.10);
    }}
    .toolbar {{
      display: grid;
      grid-template-columns: repeat(2, minmax(160px, 1fr));
      gap: 16px;
      padding: 16px;
      border-bottom: 1px solid rgba(0,0,0,0.08);
    }}
    label {{ color: #6e6e73; font-size: 13px; }}
    input {{ width: 100%; accent-color: #0071e3; }}
    .stage {{
      height: 680px;
      overflow: hidden;
      perspective: 1200px;
      display: grid;
      place-items: center;
      background:
        linear-gradient(90deg, rgba(0,0,0,0.035) 1px, transparent 1px),
        linear-gradient(0deg, rgba(0,0,0,0.035) 1px, transparent 1px),
        #ffffff;
      background-size: 36px 36px;
    }}
    .scene {{
      position: relative;
      width: {width}px;
      height: {height}px;
      transform-style: preserve-3d;
      transform: rotateX(var(--rx, 58deg)) rotateZ(var(--rz, -34deg)) scale(0.82);
      transition: transform 180ms ease;
    }}
    .block {{
      position: absolute;
      left: calc(var(--x) * 1px);
      top: calc(var(--y) * 1px);
      width: calc(var(--w) * 1px);
      height: calc(var(--h) * 1px);
      min-width: 3px;
      min-height: 3px;
      background: color-mix(in srgb, var(--c), white 14%);
      border: 1px solid rgba(0,0,0,0.32);
      transform: translateZ(calc(var(--z) * 1px));
      box-shadow:
        calc(var(--t) * 1px) calc(var(--t) * 1px) 0 color-mix(in srgb, var(--c), black 22%),
        0 12px 24px rgba(0,0,0,0.10);
      opacity: 0.86;
    }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 14px; }}
    .legend span {{ display: inline-flex; align-items: center; gap: 6px; font-size: 13px; }}
    .legend i {{ width: 14px; height: 14px; border: 1px solid #1d1d1f; display: inline-block; border-radius: 4px; }}
  </style>
</head>
<body>
  <main>
    <h1>Text-to-GDS 3D Stack Preview</h1>
    <p>{html.escape(gds_path.name)} - {len(boxes)} extracted layer boxes</p>
    <div class="viewer">
      <div class="toolbar">
        <label>Rotate X<input id="rx" type="range" min="35" max="75" value="58"></label>
        <label>Rotate Z<input id="rz" type="range" min="-58" max="-12" value="-34"></label>
      </div>
      <div class="stage" role="img" aria-label="3D process stack preview">
        <div id="scene" class="scene">
          {''.join(blocks)}
        </div>
      </div>
    </div>
    <div class="legend">{''.join(legend_items)}</div>
  </main>
  <script>
    const scene = document.querySelector("#scene");
    const rx = document.querySelector("#rx");
    const rz = document.querySelector("#rz");
    function update() {{
      scene.style.setProperty("--rx", `${{rx.value}}deg`);
      scene.style.setProperty("--rz", `${{rz.value}}deg`);
    }}
    rx.addEventListener("input", update);
    rz.addEventListener("input", update);
    update();
  </script>
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
