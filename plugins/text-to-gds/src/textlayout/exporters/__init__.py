"""Exporters: Geometry IR → output artifacts (GDS, SVG, PNG, JSON)."""

from __future__ import annotations

from textlayout.exporters.gds_exporter import GdsExporter
from textlayout.exporters.json_exporter import JsonExporter
from textlayout.exporters.png_exporter import PngExporter
from textlayout.exporters.svg_exporter import SvgExporter
from textlayout.ports.exporter import Exporter

__all__ = [
    "Exporter",
    "GdsExporter",
    "JsonExporter",
    "PngExporter",
    "SvgExporter",
    "default_exporters",
]


def default_exporters() -> dict[str, Exporter]:
    """Build the built-in exporter map keyed by format name."""
    exporters: list[Exporter] = [GdsExporter(), JsonExporter(), SvgExporter(), PngExporter()]
    return {exp.format: exp for exp in exporters}
