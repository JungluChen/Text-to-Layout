from __future__ import annotations

from text_to_gds.device_library import JPA
from text_to_gds.reference_compare import golden_compare


def test_jpa_matches_golden_topology_without_fake_solver_data() -> None:
    report = golden_compare(JPA(frequency_ghz=6.0, target_gain_db=20.0, bandwidth_mhz=200.0), "jpa")
    assert report["device_family"] == "jpa"
    assert report["topology_score"] >= 0.75
    assert not any("decorative" in warning.lower() for warning in report["fabrication_warnings"])
    assert "frequency_range_ghz" in report["parameter_error"]
    assert report["parameter_error"]["frequency_range_ghz"]["status"] == "in_range"
    assert "pump path identified" not in report["missing_features"]
    assert "signal path identified" not in report["missing_features"]


def test_jpa_missing_current_path_is_reported_not_filled() -> None:
    report = golden_compare(
        {
            "pcell": "lumped_element_jpa_seed",
            "info": {
                "device_type": "jpa",
                "metal_nets": {"rf_feed": ["signal"], "flux_bias": ["flux"]},
            },
        },
        "jpa",
    )
    assert report["topology_score"] < 1.0
    assert any("SQUID current path" in warning for warning in report["fabrication_warnings"])
    assert any(row["status"] == "missing_generated_value" for row in report["parameter_error"].values())
