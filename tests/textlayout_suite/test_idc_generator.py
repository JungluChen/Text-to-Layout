"""IDC generator geometry tests."""

from __future__ import annotations

from textlayout.generators import IDCGenerator
from textlayout.knowledge import GENERIC_2METAL
from textlayout.schemas.dsl import IDCSpec


def _geom(**kw: object):
    base = dict(finger_pairs=22, finger_width_um=4, gap_um=2, overlap_um=250, bus_width_um=25)
    base.update(kw)
    params = IDCSpec(**base)  # type: ignore[arg-type]
    return IDCGenerator().generate(params, GENERIC_2METAL, origin=(0.0, 0.0))


def test_idc_polygon_count() -> None:
    geom = _geom()
    # 2 buses + 2*finger_pairs fingers
    assert len(geom.polygons) == 2 + 2 * 22
    assert geom.layers() == ("M1",)


def test_idc_has_two_ports() -> None:
    geom = _geom()
    assert len(geom.ports) == 2
    assert {p.name for p in geom.ports} == {"P1", "P2"}
    assert geom.metadata["min_ports"] == 2


def test_idc_bounding_box_positive() -> None:
    box = _geom().bbox()
    assert box.width > 0
    assert box.height > 0


def test_idc_is_deterministic() -> None:
    assert _geom().polygons == _geom().polygons


def test_idc_metadata_capacitance_is_labelled_low_confidence() -> None:
    md = _geom().metadata
    assert md["capacitance_method"] == "bahl_alley_quasi_static"
    assert md["analytical_estimate"] is True
    assert 0.5 < md["estimated_capacitance_pf"] < 0.9
