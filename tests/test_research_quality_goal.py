from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from text_to_gds.cpw_physics import synthesize_cpw
from text_to_gds.design_intent import synthesize_design_intent, write_design_intent
from text_to_gds.resonator_checker import check_resonator
from text_to_gds.rf_validation import analyze_rf_trace
from text_to_gds.review.committee import REVIEWERS, review_committee


def _complete_jpa_inputs() -> dict:
    return {
        "jc_ua_per_um2": 2.0,
        "junction_width_um": 0.22,
        "junction_height_um": 0.22,
        "junction_count": 2,
        "center_width_um": 10.0,
        "gap_um": 6.0,
        "ground_width_um": 500.0,
        "substrate": "high_resistivity_silicon",
        "epsilon_r": 11.45,
        "substrate_thickness_um": 254.0,
        "pump_frequency_ghz": 12.0,
        "pump_power_dbm": -70.0,
        "pump_mode": "flux",
        "package_clearance_um": 250.0,
        "wirebond_pads": True,
    }


def test_design_intent_fails_before_geometry_when_physics_is_missing(tmp_path):
    intent = synthesize_design_intent("Design a 6 GHz JPA with 20 dB gain and 500 MHz bandwidth")
    assert intent["status"] == "failed"
    assert "Jc" in " ".join(intent["blockers"])
    written = write_design_intent(intent, tmp_path / "design_intent.json")
    assert json.loads((tmp_path / "design_intent.json").read_text())["status"] == "failed"
    assert written["result_path"].endswith("design_intent.json")


def test_design_intent_synthesizes_traceable_lc_q_and_cpw():
    intent = synthesize_design_intent(
        "Design a 6 GHz JPA with 20 dB gain and 500 MHz bandwidth",
        inputs=_complete_jpa_inputs(),
    )
    assert intent["status"] == "ready", intent["blockers"]
    physics = intent["physics"]
    assert physics["critical_current_a"] == pytest.approx(0.1936e-6)
    assert physics["josephson_inductance_h"] > 0.0
    assert physics["capacitance_required_f"] > 0.0
    f0 = 1.0 / (
        2.0
        * math.pi
        * math.sqrt(physics["inductance_required_h"] * physics["capacitance_required_f"])
    )
    assert f0 == pytest.approx(6e9)
    assert physics["coupling_q"] == pytest.approx(12.0)
    assert physics["cpw"]["status"] == "ok"


def test_cpw_synthesis_rejects_wrong_impedance():
    result = synthesize_cpw(
        center_width_um=2.0,
        gap_um=20.0,
        ground_width_um=500.0,
        epsilon_r=11.45,
        substrate_thickness_um=254.0,
        frequency_ghz=6.0,
        impedance_tolerance_ohm=2.5,
    )
    assert result["status"] == "failed"
    assert result["validation"]["passed"] is False


def test_resonator_checker_requires_all_six_physical_conditions():
    sidecar = {
        "info": {
            "boundary_condition": "open_at_coupler_shorted_at_via12",
            "layers": {"short_via": [7, 0]},
            "electrical_length_um": 5000.0,
            "target_frequency_ghz": 6.0,
            "coupling_length_um": 200.0,
            "coupling_gap_um": 6.0,
        },
        "ports": [{"name": "resonator_open"}, {"name": "feed_out"}],
    }
    extraction = {
        "linear_circuit": {"resonance_frequency": 6e9, "q_external": 1000.0},
        "cpw": {"quarter_wave_length_um": 5000.0},
    }
    result = check_resonator(sidecar, extraction)
    assert result["status"] == "PASS"
    assert len(result["checks"]) == 6


def test_rf_feature_validation_rejects_flat_and_passive_gain():
    frequencies = [5.0, 5.5, 6.0, 6.5, 7.0]
    flat = analyze_rf_trace(
        frequencies,
        {"s21_db": [0.0] * 5},
        active=False,
        require_resonance=True,
    )
    assert flat["status"] == "failed"
    assert "S21 response is flat" in flat["errors"]
    assert "passive network has positive S21 gain" not in flat["errors"]


def test_committee_has_five_agents_and_requires_literature():
    assert set(REVIEWERS) == {"physics", "microwave", "fabrication", "measurement", "literature"}
    committee = review_committee(
        {
            "device": "cpw_resonator",
            "sidecar": {
                "info": {
                    "device_type": "cpw_resonator",
                    "has_ground_plane": True,
                    "wirebond_pads": True,
                    "package_clearance_um": 250.0,
                },
                "ports": [{"name": "input_pad"}, {"name": "output_pad"}],
            },
            "drc": {"status": "passed", "violations": []},
            "simulation": {
                "frequencies_ghz": [5.0, 5.5, 6.0, 6.5, 7.0],
                "s_parameters_db": {
                    "s11_db": [-20.0] * 5,
                    "s21_db": [-1.0, -2.0, -15.0, -2.0, -1.0],
                    "s12_db": [-1.0, -2.0, -15.0, -2.0, -1.0],
                    "s22_db": [-20.0] * 5,
                },
            },
        }
    )
    assert committee["approved"] is False
    assert any("literature" in item["agent"] for item in committee["blockers"])


def test_prompt_workflow_writes_intent_before_gds_and_reviews_solver_failure(monkeypatch, tmp_path):
    import text_to_gds.server as server

    monkeypatch.setattr(server, "ARTIFACT_ROOT", tmp_path)
    missing = server.run_design_workflow(
        "Design a 6 GHz JPA with 20 dB gain and 200 MHz bandwidth",
        output_name="missing.gds",
    )
    assert missing["stage"] == "design_intent"
    assert (tmp_path / "missing.design_intent.json").is_file()
    assert not (tmp_path / "missing.gds").exists()

    result = server.run_design_workflow(
        "Design a 6 GHz JPA with 20 dB gain and 200 MHz bandwidth",
        output_name="candidate.gds",
        parameters={
            "junction_width": 0.22,
            "junction_height": 0.22,
            "cpw_trace_width": 10.0,
            "cpw_gap": 6.0,
        },
        jc_ua_per_um2=2.0,
        substrate="high_resistivity_silicon",
        epsilon_r=11.45,
        substrate_thickness_um=254.0,
        ground_width_um=500.0,
        package_clearance_um=250.0,
        pump_frequency_ghz=12.0,
        pump_power_dbm=-130.0,
        pump_mode="flux",
        simulator="none",
        literature_comparison={
            "references": ["reference-jpa"],
            "comparisons": [{"parameter": "frequency_ghz", "generated": 6.0, "reference": 6.0}],
        },
    )
    assert result["status"] == "failed"
    assert result["design_intent"]["status"] == "ready"
    assert Path(result["compile"]["gds_path"]).is_file()
    assert result["simulation"]["reason"] == "solver execution unavailable"
    assert Path(result["review"]["result_path"]).is_file()
