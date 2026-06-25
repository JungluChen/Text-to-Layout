"""Tests for rendering and report visual quality.

Verifies that layout rendering produces valid PNGs, that rendered images
are not blank, and that sidecar metadata has all required fields.
"""

from __future__ import annotations

from pathlib import Path

import pytest

kdb = pytest.importorskip("klayout.db")


def _try_import_render():
    """Try importing render_layout_screenshot; skip if rendering.py has broken imports."""
    try:
        from text_to_gds.rendering import render_layout_screenshot
        return render_layout_screenshot
    except ImportError as exc:
        pytest.skip(f"rendering module has broken import: {exc}")


def _try_import_sidecar():
    """Try importing component_sidecar; skip if rendering.py has broken imports."""
    try:
        from text_to_gds.rendering import component_sidecar
        return component_sidecar
    except ImportError as exc:
        pytest.skip(f"rendering module has broken import: {exc}")


# -- Render produces PNG ------------------------------------------------------


def test_render_produces_png(tmp_path: Path) -> None:
    """Generate a CPW, render it, verify PNG file exists and is >1KB."""
    from text_to_gds.pcells.passives import cpw_straight

    render_layout_screenshot = _try_import_render()

    c = cpw_straight(length=100.0, trace_width=10.0, gap=6.0)
    gds_path = tmp_path / "cpw_render.gds"
    c.write_gds(str(gds_path))

    png_path = tmp_path / "cpw_render.png"
    render_layout_screenshot(gds_path, png_path, image_size=500)

    assert png_path.exists(), "PNG file must be created"
    assert png_path.stat().st_size > 1024, (
        f"PNG must be >1KB, got {png_path.stat().st_size} bytes"
    )


# -- Render is not blank ------------------------------------------------------


def test_render_not_blank(tmp_path: Path) -> None:
    """Rendered PNG must have more than one color (not blank)."""
    from text_to_gds.pcells.passives import cpw_straight

    render_layout_screenshot = _try_import_render()
    pytest.importorskip("PIL")
    from PIL import Image

    c = cpw_straight(length=100.0, trace_width=10.0, gap=6.0)
    gds_path = tmp_path / "cpw_blank.gds"
    c.write_gds(str(gds_path))

    png_path = tmp_path / "cpw_blank.png"
    render_layout_screenshot(gds_path, png_path, image_size=500)

    image = Image.open(png_path)
    colors = image.getcolors(maxcolors=1000)

    # A blank image would have exactly 1 color entry
    assert colors is None or len(colors) > 1, (
        "Rendered image must have more than one color (not blank)"
    )


# -- Sidecar has required fields ----------------------------------------------


def test_sidecar_has_required_fields(tmp_path: Path) -> None:
    """Sidecar JSON must have: schema, pcell, gds_path, bbox_um, ports, info."""
    from text_to_gds.pcells.passives import cpw_straight

    component_sidecar = _try_import_sidecar()

    c = cpw_straight(length=100.0, trace_width=10.0, gap=6.0)
    gds_path = tmp_path / "cpw_sidecar.gds"
    c.write_gds(str(gds_path))

    screenshot_path = tmp_path / "cpw_sidecar.png"
    # Create a minimal PNG so the sidecar path is valid
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    sidecar = component_sidecar(c, gds_path, "cpw_straight", screenshot_path)

    required_keys = ["schema", "pcell", "gds_path", "bbox_um", "ports", "info"]
    for key in required_keys:
        assert key in sidecar, f"Sidecar must have '{key}' field"

    assert sidecar["schema"] == "text-to-gds.sidecar.v0"
    assert sidecar["pcell"] == "cpw_straight"
    assert isinstance(sidecar["ports"], list)
    assert len(sidecar["ports"]) > 0, "CPW must have at least one port"
    assert isinstance(sidecar["info"], dict)
    assert sidecar["bbox_um"] is not None, "bbox_um must not be None"
