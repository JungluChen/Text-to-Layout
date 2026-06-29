"""Professional mask-like layer rendering and chip-frame utilities."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from text_to_gds.process import CHIP_BOUNDARY, KEEPOUT, Layer


@lru_cache(maxsize=8)
def annotation_font(size: int = 13) -> Any:
    """Return a readable TrueType font for scale bars and layer legends."""
    from PIL import ImageFont

    candidates = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    try:
        from matplotlib import font_manager

        return ImageFont.truetype(font_manager.findfont("DejaVu Sans"), size=size)
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


@dataclass(frozen=True)
class LayerStyle:
    """Visual style for one GDS layer in mask-like rendering."""

    name: str
    layer: Layer
    fill_rgba: tuple[int, int, int, int]
    outline_rgba: tuple[int, int, int, int]
    hatch: str
    legend_label: str
    render_order: int
    visible: bool


MASK_STYLES: dict[Layer, LayerStyle] = {
    (3, 0): LayerStyle(
        name="M1",
        layer=(3, 0),
        fill_rgba=(70, 130, 210, 200),
        outline_rgba=(40, 80, 160, 240),
        hatch="solid",
        legend_label="M1 - Nb ground/bottom electrode",
        render_order=0,
        visible=True,
    ),
    (4, 0): LayerStyle(
        name="JJ",
        layer=(4, 0),
        fill_rgba=(220, 60, 60, 220),
        outline_rgba=(180, 30, 30, 255),
        hatch="cross",
        legend_label="JJ - AlOx tunnel barrier",
        render_order=2,
        visible=True,
    ),
    (5, 0): LayerStyle(
        name="M2",
        layer=(5, 0),
        fill_rgba=(50, 170, 100, 200),
        outline_rgba=(30, 120, 70, 240),
        hatch="solid",
        legend_label="M2 - Nb CPW/top electrode",
        render_order=1,
        visible=True,
    ),
    (6, 0): LayerStyle(
        name="M3",
        layer=(6, 0),
        fill_rgba=(140, 80, 220, 180),
        outline_rgba=(100, 50, 180, 230),
        hatch="solid",
        legend_label="M3 - Nb global routing",
        render_order=3,
        visible=True,
    ),
    (7, 0): LayerStyle(
        name="VIA12",
        layer=(7, 0),
        fill_rgba=(240, 180, 40, 210),
        outline_rgba=(200, 140, 10, 255),
        hatch="dots",
        legend_label="VIA12 - M1/M2 via",
        render_order=4,
        visible=True,
    ),
    (8, 0): LayerStyle(
        name="VIA23",
        layer=(8, 0),
        fill_rgba=(250, 130, 50, 210),
        outline_rgba=(210, 100, 20, 255),
        hatch="dots",
        legend_label="VIA23 - M2/M3 via",
        render_order=5,
        visible=True,
    ),
    (9, 0): LayerStyle(
        name="UNDERCUT",
        layer=(9, 0),
        fill_rgba=(180, 180, 80, 120),
        outline_rgba=(140, 140, 50, 180),
        hatch="diagonal",
        legend_label="UNDERCUT - resist opening",
        render_order=6,
        visible=True,
    ),
    (10, 0): LayerStyle(
        name="MARKER",
        layer=(10, 0),
        fill_rgba=(100, 100, 100, 80),
        outline_rgba=(80, 80, 80, 120),
        hatch="none",
        legend_label="MARKER - annotation only",
        render_order=99,
        visible=False,
    ),
    CHIP_BOUNDARY: LayerStyle(
        name="CHIP_BOUNDARY",
        layer=CHIP_BOUNDARY,
        fill_rgba=(0, 0, 0, 0),
        outline_rgba=(200, 200, 200, 255),
        hatch="none",
        legend_label="CHIP - die boundary",
        render_order=100,
        visible=True,
    ),
    KEEPOUT: LayerStyle(
        name="KEEPOUT",
        layer=KEEPOUT,
        fill_rgba=(0, 0, 0, 0),
        outline_rgba=(255, 60, 60, 200),
        hatch="none",
        legend_label="KEEPOUT - exclusion zone",
        render_order=97,
        visible=True,
    ),
}

SUBSTRATE_COLOR: tuple[int, int, int, int] = (20, 22, 30, 255)
ANNOTATION_COLOR: tuple[int, int, int, int] = (200, 200, 200, 255)


def style_for_layer(layer: Layer) -> LayerStyle:
    """Return the mask style for *layer*, with a fallback for unknown layers."""
    if layer in MASK_STYLES:
        return MASK_STYLES[layer]
    seed = (layer[0] * 97 + layer[1] * 53) % 255
    return LayerStyle(
        name=f"L{layer[0]}_{layer[1]}",
        layer=layer,
        fill_rgba=(60 + seed % 100, 60 + (seed * 3) % 100, 60 + (seed * 7) % 100, 160),
        outline_rgba=(40 + seed % 80, 40 + (seed * 3) % 80, 40 + (seed * 7) % 80, 200),
        hatch="solid",
        legend_label=f"Layer {layer[0]}/{layer[1]}",
        render_order=50,
        visible=True,
    )


def visible_layers() -> list[LayerStyle]:
    """Return all visible layer styles sorted by render order."""
    return sorted(
        [style for style in MASK_STYLES.values() if style.visible],
        key=lambda style: style.render_order,
    )


def draw_scale_bar(
    draw: Any,
    canvas_width: int,
    canvas_height: int,
    scale_um_per_px: float,
    *,
    margin: int = 30,
    bar_height: int = 6,
) -> None:
    """Draw a scale bar in the bottom-left corner of the image."""
    target_px = canvas_width * 0.15
    target_um = target_px * scale_um_per_px
    nice_values = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]
    bar_um = min(nice_values, key=lambda value: abs(value - target_um))
    bar_px = int(bar_um / scale_um_per_px)
    if bar_px < 20:
        return

    x0 = margin
    y0 = canvas_height - margin - bar_height
    x1 = x0 + bar_px
    y1 = y0 + bar_height

    draw.rectangle([x0, y0, x1, y1], fill=(255, 255, 255, 230), outline=(180, 180, 180, 255))
    for index in range(0, bar_px, max(bar_px // 5, 1)):
        tick_x = x0 + index
        draw.line([(tick_x, y0), (tick_x, y0 - 3)], fill=(200, 200, 200, 200), width=1)

    label = f"{bar_um:g} um" if bar_um >= 1 else f"{bar_um * 1000:g} nm"
    draw.text((x0, y0 - 18), label, fill=ANNOTATION_COLOR[:3], font=annotation_font())


def draw_layer_legend(
    draw: Any,
    canvas_width: int,
    canvas_height: int,
    active_layers: set[Layer],
    *,
    margin: int = 16,
    swatch_size: int = 14,
    line_height: int = 20,
) -> None:
    """Draw a compact layer legend in the top-right corner."""
    styles = [style_for_layer(layer) for layer in sorted(active_layers) if style_for_layer(layer).visible]
    if not styles:
        return

    x0 = canvas_width - margin - 260
    y = margin + 4
    for style in styles:
        draw.rectangle(
            [x0, y, x0 + swatch_size, y + swatch_size],
            fill=style.fill_rgba,
            outline=style.outline_rgba,
        )
        draw.text(
            (x0 + swatch_size + 6, y - 1),
            style.legend_label,
            fill=ANNOTATION_COLOR[:3],
            font=annotation_font(),
        )
        y += line_height


def chip_frame_polygons(
    width_um: float,
    height_um: float,
    *,
    frame_width_um: float = 4.0,
) -> list[tuple[list[tuple[float, float]], Layer]]:
    """Return chip-boundary outline polygons for a rectangular die."""
    half_w, half_h = width_um / 2.0, height_um / 2.0
    frame = frame_width_um
    return [
        ([(-half_w, -half_h), (half_w, -half_h), (half_w, -half_h + frame), (-half_w, -half_h + frame)], CHIP_BOUNDARY),
        ([(-half_w, half_h - frame), (half_w, half_h - frame), (half_w, half_h), (-half_w, half_h)], CHIP_BOUNDARY),
        ([(-half_w, -half_h), (-half_w + frame, -half_h), (-half_w + frame, half_h), (-half_w, half_h)], CHIP_BOUNDARY),
        ([(half_w - frame, -half_h), (half_w, -half_h), (half_w, half_h), (half_w - frame, half_h)], CHIP_BOUNDARY),
    ]
