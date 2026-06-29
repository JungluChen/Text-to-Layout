"""GDS export tests (real gdsfactory round-trip)."""

from __future__ import annotations

from pathlib import Path

from textlayout.exporters import GdsExporter
from textlayout.generators import IDCGenerator
from textlayout.knowledge import GENERIC_2METAL
from textlayout.schemas.dsl import IDCSpec


def _idc_geometry():
    params = IDCSpec(finger_pairs=8, finger_width_um=4, gap_um=2, overlap_um=100, bus_width_um=20)
    return IDCGenerator().generate(params, GENERIC_2METAL, origin=(0.0, 0.0))


def test_gds_file_is_written_and_nonempty(tmp_path: Path) -> None:
    out = tmp_path / "idc.gds"
    written = GdsExporter().write(_idc_geometry(), GENERIC_2METAL, out)
    assert written.exists()
    assert written.stat().st_size > 0


def test_gds_component_has_ports(tmp_path: Path) -> None:
    component = GdsExporter().build_component(_idc_geometry(), GENERIC_2METAL)
    assert len(component.ports) == 2
