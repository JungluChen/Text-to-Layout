from __future__ import annotations

from text_to_gds.device_library import Resonator
from text_to_gds.reference_compare import golden_compare


def test_cpw_reports_analytic_reference_and_missing_em() -> None:
    report = golden_compare(Resonator(frequency_ghz=6.0, impedance_ohm=50.0), "cpw")
    assert report["device_family"] == "cpw"
    assert "target_z0_ohm" in report["parameter_error"]
    assert report["parameter_error"]["target_z0_ohm"]["status"] == "compared"
    assert any("EM Z0 comparison missing" in item for item in report["missing_features"])
    assert report["comparisons"]


def test_cpw_does_not_claim_em_agreement_without_em_result() -> None:
    report = golden_compare(
        {"pcell": "cpw_resonator", "extraction": {"Z0": 50.0, "physical_length_um": 5000.0}},
        "cpw",
    )
    assert "em_z0_ohm" not in report["generated_parameters"]
    assert any("no EM result supplied" in item for item in report["missing_features"])
