"""CPW generator geometry tests (deterministic shape correctness)."""

from __future__ import annotations

from textlayout.generators import CPWGenerator
from textlayout.knowledge import GENERIC_2METAL
from textlayout.schemas.dsl import CPWSpec


def _geom(**kw: float):
    params = CPWSpec(center_width_um=10, gap_um=6, length_um=1000, ground_width_um=50, **kw)  # type: ignore[arg-type]
    return CPWGenerator().generate(params, GENERIC_2METAL, origin=(0.0, 0.0))


def test_cpw_has_signal_and_two_grounds_on_metal() -> None:
    geom = _geom()
    assert len(geom.polygons) == 3
    assert geom.layers() == ("M1",)


def test_cpw_bounding_box_matches_formula() -> None:
    geom = _geom()
    bbox = geom.bbox()
    # total width = 2*(ground_width + gap) + center = 2*(50+6) + 10 = 122
    assert bbox.width == 122.0
    assert bbox.height == 1000.0
    assert bbox.center == (0.0, 500.0)


def test_cpw_gap_is_symmetric() -> None:
    geom = _geom()
    signal = geom.polygons[0].bbox
    assert signal.xmin == -5.0
    assert signal.xmax == 5.0


def test_cpw_is_deterministic() -> None:
    assert _geom().polygons == _geom().polygons
