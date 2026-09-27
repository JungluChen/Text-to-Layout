"""CPW analytical model selection never upgrades evidence confidence."""
import pytest

from textlayout import build_default_workflow
from textlayout.generators import cpw
from textlayout.schemas.dsl import LayoutSpec
from textlayout.research.formulas import cpw_skrf_z0, cpw_z0


def generate():
    return build_default_workflow().run(LayoutSpec(component="CPW", parameters={
        "center_width_um": 10, "gap_um": 6, "length_um": 1000}), formats=()).geometry


def test_prefers_actual_skrf_model():
    pytest.importorskip("skrf")
    geometry = generate()
    expected = cpw_skrf_z0(10, 6, 11.9)
    assert expected is not None
    assert geometry.metadata["estimated_z0_ohm"] == round(expected[0], 4)
    assert "scikit-rf" in geometry.metadata["analytical_model"]
    assert geometry.metadata["method"] == "analytical"
    assert geometry.metadata["confidence"] == 0.65


def test_absent_skrf_is_explicit_fallback(monkeypatch):
    monkeypatch.setattr(cpw, "cpw_skrf_z0", lambda *args: None)
    geometry = generate()
    assert geometry.metadata["estimated_z0_ohm"] == round(cpw_z0(10, 6, 11.9)[0], 4)
    assert "fallback" in geometry.metadata["analytical_model"]
    assert geometry.metadata["method"] == "analytical"
    assert geometry.metadata["confidence"] == 0.65
