"""Exporter tests: JSON structure + determinism, SVG well-formedness."""

from __future__ import annotations

import json

from textlayout.exporters import JsonExporter, SvgExporter, default_exporters
from textlayout.generators import CPWGenerator
from textlayout.knowledge import GENERIC_2METAL
from textlayout.schemas.dsl import CPWSpec


def _geom():
    params = CPWSpec(center_width_um=10, gap_um=6, length_um=1000)
    return CPWGenerator().generate(params, GENERIC_2METAL, origin=(0.0, 0.0))


def test_json_exporter_structure() -> None:
    doc = json.loads(JsonExporter().render(_geom(), GENERIC_2METAL))
    assert doc["schema"] == "textlayout.geometry.v1"
    assert doc["bbox_um"]["width"] == 122.0
    assert len(doc["polygons"]) == 3
    assert doc["layers"][0]["name"] == "M1"
    assert doc["layers"][0]["gds_layer"] == 1


def test_json_exporter_is_deterministic() -> None:
    a = JsonExporter().render(_geom(), GENERIC_2METAL)
    b = JsonExporter().render(_geom(), GENERIC_2METAL)
    assert a == b


def test_svg_exporter_is_well_formed() -> None:
    svg = SvgExporter().render(_geom(), GENERIC_2METAL)
    assert svg.startswith("<svg")
    assert svg.count("<polygon") == 3
    assert svg.rstrip().endswith("</svg>")


def test_default_exporters_keys() -> None:
    exporters = default_exporters()
    assert set(exporters) == {"gds", "json", "png", "svg"}
