"""Synthetic mask fixtures test the gate, not upstream numerical execution."""

import importlib.util
from pathlib import Path

import klayout.db as kdb
import pytest

spec = importlib.util.spec_from_file_location(
    "qm_gate", Path(__file__).resolve().parents[2] / "scripts/check_quantum_metal_transmon_gds.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(path, *, shift=0, datatype=10, extra=False):
    layout = kdb.Layout()
    layout.dbu = 0.001
    top = layout.create_cell("TOP")
    ground = kdb.Region(kdb.Box(-1000000, -1000000, 1000000, 1000000)) - kdb.Region(
        kdb.Box(-325000, -325000, 325000, 325000)
    )
    top.shapes(layout.layer(1, 0)).insert(ground)
    pads = top.shapes(layout.layer(1, datatype))
    pads.insert(kdb.Box(-227500 + shift, 15000, 227500 + shift, 105000))
    pads.insert(kdb.Box(-227500, -105000, 227500, -15000))
    if extra:
        top.shapes(layout.layer(2, 0)).insert(kdb.Box(0, 0, 10, 10))
    layout.write(str(path))


def test_empty_successful_export_is_not_geometry(tmp_path):
    path = tmp_path / "empty.gds"
    kdb.Layout().write(str(path))
    assert not module.check(path)["geometry_verified"]


def test_matching_mask_does_not_verify_junction_or_electrical_result(tmp_path):
    path = tmp_path / "valid.gds"
    fixture(path)
    report = module.check(path)
    assert report["geometry_verified"]
    assert not report["junction_verified"]
    assert report["electrical_validation"] == "NOT_EVALUATED"


@pytest.mark.parametrize("changes", [{"shift": 1}, {"datatype": 11}, {"extra": True}])
def test_reject_changed_geometry_or_layers(tmp_path, changes):
    path = tmp_path / "wrong.gds"
    fixture(path, **changes)
    assert not module.check(path)["geometry_verified"]
