"""Different analytical CPW estimates must expose their own model assumptions."""
import pytest

from textlayout import build_default_workflow
from textlayout.schemas.dsl import LayoutSpec
from textlayout.research import formulas


def report():
    return build_default_workflow().run(LayoutSpec(component="CPW", parameters={
        "center_width_um": 10, "gap_um": 6, "length_um": 1000}), formats=()).research


def test_actual_optional_model_does_not_relabel_primary_estimate():
    pytest.importorskip("skrf")
    result = report()
    values = result.analytical_estimates
    assert "Simons/Hilberg" in values["analytical_backend"]
    assert values["estimated_z0_ohm"] == round(formulas.cpw_z0(10, 6, 11.9)[0], 2)
    assert values["scikit_rf_substrate_height_um"] == 500.0
    assert values["scikit_rf_frequency_ghz"] == 1.0
    assert any("500 um" in assumption for assumption in result.assumptions)
    assert not any("accurate to a few percent" in limit for limit in result.limitations)


def test_missing_optional_model_has_no_finite_substrate_comparison(monkeypatch):
    monkeypatch.setattr(formulas, "cpw_skrf_z0", lambda *args, **kwargs: None)
    result = report()
    assert "Simons/Hilberg" in result.analytical_estimates["analytical_backend"]
    assert "scikit_rf_z0_ohm" not in result.analytical_estimates
    assert not any("500 um" in assumption for assumption in result.assumptions)
