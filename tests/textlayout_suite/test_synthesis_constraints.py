"""Regressions from the independently checked 64-case audit population."""

import json

import pytest

from textlayout import build_from_text_workflow
from textlayout.generators._path import orthogonal_path_rectangles
from textlayout.optimization.cpw import size_cpw
from textlayout.research.formulas import cpw_z0
from textlayout.verification.klayout_readback import ReadbackCheck, ReadbackResult


@pytest.mark.parametrize("end", [(20, 0), (-20, 0), (0, 20), (0, -20)])
def test_path_is_invariant_under_reversal(end):
    forward = orthogonal_path_rectangles("M1", [(0, 0), end], 4)
    reverse = orthogonal_path_rectangles("M1", [end, (0, 0)], 4)
    assert forward == reverse


@pytest.mark.parametrize("impedance", [30, 40, 50, 60])
@pytest.mark.parametrize("gap", [2, 4, 6, 8])
def test_cpw_preserves_impedance_and_constraints(impedance, gap):
    p = size_cpw(impedance, 11.9, min_width_um=12, min_gap_um=gap)
    z, _ = cpw_z0(p["center_width_um"], p["gap_um"], 11.9)
    assert z == pytest.approx(impedance, rel=0.001)
    assert p["center_width_um"] >= 12
    assert p["gap_um"] >= gap
    assert round(p["center_width_um"] * 1000) % 2 == 0


def test_spiral_exports_one_connected_full_width_conductor(tmp_path):
    import klayout.db as kdb

    result = build_from_text_workflow().run(
        "Create a 1 nH spiral inductor with 2 turns, 4 um trace width and 2 um spacing",
        tmp_path, execute_solver=False)
    assert result.ok
    readback = json.loads((tmp_path / "klayout_readback.json").read_text())
    assert readback["status"] == "pass"
    layout = kdb.Layout()
    layout.read(str(tmp_path / "output.gds"))
    metal = kdb.Region(layout.top_cell().begin_shapes_rec(layout.layer(1, 0)))
    metal.merge()
    assert metal.count() == 1
    assert metal.width_check(4000).is_empty()


def test_independent_readback_failure_reaches_final_verdict(tmp_path, monkeypatch):
    def fail_readback(path, *_args):
        return ReadbackResult(str(path), checks=[ReadbackCheck(
            "drawn_min_width", False, "Injected sub-rule feature")])

    monkeypatch.setattr("textlayout.workflow.nodes.read_back_gds", fail_readback)
    result = build_from_text_workflow().run("Create a 50 ohm CPW", tmp_path,
                                            execute_solver=False)
    assert not result.ok
    assert "Injected sub-rule feature" in result.generate.report.errors
    assert json.loads((tmp_path / "verification.json").read_text())["status"] == "fail"
