"""Geometry parity cannot be inferred from filenames, bounding boxes or area alone."""

import klayout.db as kdb
import pytest

from textlayout.verification.reference_gds import compare_gds_geometry, roundtrip_reference_gds


def sample(path, *, offset=0, second_top=False, extra_layer=False, label="P1", dbu=0.001):
    layout = kdb.Layout()
    layout.dbu = dbu
    top = layout.create_cell("TOP")
    child = layout.create_cell("CHILD")
    child.shapes(layout.layer(1, 0)).insert(kdb.Box(offset, 0, 1000 + offset, 1000))
    child.shapes(layout.layer(1, 0)).insert(kdb.Text(label, kdb.Trans(0, 0)))
    top.insert(kdb.CellInstArray(child.cell_index(), kdb.Trans(2000, 0)))
    if second_top:
        layout.create_cell("OTHER").shapes(layout.layer(1, 0)).insert(kdb.Box(0, 0, 10, 10))
    if extra_layer:
        top.shapes(layout.layer(2, 0)).insert(kdb.Box(0, 0, 10, 10))
    layout.write(str(path))


def test_hierarchical_reference_roundtrip_preserves_all_geometry(tmp_path):
    source = tmp_path / "source.gds"
    sample(source)
    result = roundtrip_reference_gds(source, tmp_path / "output.gds")
    assert result["geometry_equivalent"]
    assert result["labels_equal"]
    assert all(row["xor_area_um2"] == 0 for row in result["layers"])


@pytest.mark.parametrize("change", [{"offset": 1}, {"extra_layer": True},
                                   {"label": "WRONG"}, {"dbu": 0.002}])
def test_changed_geometry_or_units_never_pass(tmp_path, change):
    source, candidate = tmp_path / "source.gds", tmp_path / "candidate.gds"
    sample(source)
    sample(candidate, **change)
    assert not compare_gds_geometry(source, candidate)["geometry_equivalent"]


def test_multiple_top_cells_require_explicit_selection(tmp_path):
    source = tmp_path / "source.gds"
    sample(source, second_top=True)
    with pytest.raises(ValueError, match="explicit cell"):
        roundtrip_reference_gds(source, tmp_path / "output.gds")
    assert roundtrip_reference_gds(source, tmp_path / "output.gds", cell="TOP")["geometry_equivalent"]
