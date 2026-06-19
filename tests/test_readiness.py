from __future__ import annotations

import json

from text_to_gds.validation import build_validation_report


def test_readiness_block_present_with_six_stages():
    report = build_validation_report()
    readiness = report["readiness"]
    assert readiness["trl_scale"] == 9
    assert readiness["technology_readiness_level"] == 1
    stages = [stage["stage"] for stage in readiness["stages"]]
    assert stages == ["Layout", "DRC", "Extraction", "Circuit simulation", "EM extraction", "Measurement"]


def test_downstream_evidence_is_gated_by_upstream_stages(tmp_path):
    em = tmp_path / "device.pyaedt.json"
    em.write_text(json.dumps({"status": "solved", "s_parameters": {"s21": [0.1]}}), encoding="utf-8")
    measurement = tmp_path / "device.fit.json"
    measurement.write_text(
        json.dumps({"fit": {"fit_kind": "resonator", "f0_ghz": 6.0, "center_frequency_ghz": 6.0}}),
        encoding="utf-8",
    )
    report = build_validation_report(em_path=em, measurement_path=measurement)
    readiness = report["readiness"]
    stage_by_name = {stage["stage"]: stage for stage in readiness["stages"]}
    # The EM and measurement evidence is fully present...
    assert stage_by_name["EM extraction"]["percent"] == 100.0
    assert stage_by_name["Measurement"]["percent"] == 100.0
    # ...but the TRL stays gated because layout/DRC upstream have no evidence.
    assert readiness["technology_readiness_level"] == 1
