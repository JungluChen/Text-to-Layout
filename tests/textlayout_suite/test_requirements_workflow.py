"""Goals must honor typed physical quantities and reject unimplemented conditions."""

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from textlayout import build_default_workflow
from textlayout.backend.app import create_app
from textlayout.backend.settings import Settings
from textlayout.cli import main
from textlayout.requirements import DesignRequirements, run_requirements


@pytest.mark.parametrize("quantity,value,component", [
    ("capacitance_pf", 0.6, "IDC"), ("inductance_nh", 3, "SpiralInductor"),
    ("impedance_ohm", 50, "CPW"), ("quarter_wave_frequency_ghz", 6, "QuarterWaveResonator"),
])
def test_goal_selects_and_executes_supported_topology(tmp_path, quantity, value, component):
    requirements = DesignRequirements(quantity=quantity, value=value, min_width_um=4, min_gap_um=3)
    result = run_requirements(requirements, tmp_path, workflow=build_default_workflow(),
                              execute_solver=False)
    assert result.ok
    assert result.intent.component == component
    assert value in result.intent.target.values()
    assert result.intent.notes
    assert json.loads((tmp_path / "requirements.json").read_text())["quantity"] == quantity
    assert json.loads((tmp_path / "klayout_readback.json").read_text())["status"] == "pass"


def test_cpw_selects_a_length_that_fits_the_requested_envelope(tmp_path):
    requirements = DesignRequirements(quantity="impedance_ohm", value=50,
                                      max_bbox_height_um=500, max_bbox_width_um=500)
    result = run_requirements(requirements, tmp_path, workflow=build_default_workflow(),
                              execute_solver=False)
    assert result.ok
    assert result.spec.parameters["length_um"] == 500
    assert result.generate.geometry.bbox().height <= 500


def test_unsatisfied_footprint_is_a_failed_design(tmp_path):
    requirements = DesignRequirements(quantity="capacitance_pf", value=0.6, max_bbox_width_um=1)
    result = run_requirements(requirements, tmp_path, workflow=build_default_workflow(),
                              execute_solver=False)
    assert not result.ok
    assert any("max_bbox_width_um" in error for error in result.generate.report.errors)
    assert json.loads((tmp_path / "verification.json").read_text())["status"] == "fail"


@pytest.mark.parametrize("target", [1e-9, 10000])
def test_unreachable_target_fails_before_expensive_geometry(tmp_path, target):
    from textlayout.errors import InvalidParametersError

    requirements = DesignRequirements(quantity="capacitance_pf", value=target)
    with pytest.raises(InvalidParametersError, match="unreachable"):
        run_requirements(requirements, tmp_path, workflow=build_default_workflow(),
                          execute_solver=False)
    assert not (tmp_path / "output.gds").exists()
    assert not json.loads((tmp_path / "requirements_feasibility.json").read_text())["converged"]


def test_out_of_range_goal_is_a_structured_api_error(tmp_path):
    client = TestClient(create_app(settings=Settings(workspace=tmp_path)))
    response = client.post("/layout/from-goal", json={"requirements": {
        "quantity": "impedance_ohm", "value": 1e9}, "execute_solver": False})
    assert response.status_code == 400
    assert response.json()["error"] == "InvalidParametersError"


@pytest.mark.parametrize("field,value", [("value", True), ("value", float("inf")),
                                         ("value", -3), ("value", "50"),
                                         ("min_gap_um", 0), ("temperature_mk", 10)])
def test_bad_or_unsupported_requirements_are_not_ignored(field, value):
    with pytest.raises(ValidationError):
        DesignRequirements.model_validate({"quantity": "impedance_ohm", "value": 50, field: value})


def test_conflicting_frequencies_are_rejected():
    with pytest.raises(ValidationError, match="must agree"):
        DesignRequirements(quantity="quarter_wave_frequency_ghz", value=6, operating_frequency_ghz=5)


def test_requested_minima_cannot_weaken_the_process_rules():
    req = DesignRequirements(quantity="capacitance_pf", value=0.6, min_width_um=0.1, min_gap_um=0.1)
    intent = req.design_intent(build_default_workflow())
    assert intent.constraints["min_width_um"] == 2
    assert intent.constraints["min_gap_um"] == 2


def test_goal_cli_writes_a_reviewable_layout(tmp_path, capsys):
    source = tmp_path / "requirements.json"
    source.write_text(json.dumps({"quantity": "impedance_ohm", "value": 50, "min_gap_um": 8}))
    code = main(["design", str(source), "--out", str(tmp_path / "layout"), "--no-solver"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["component"] == "CPW"
    assert payload["verification"]["status"] == "pass"


def test_goal_api_retains_conditions_and_rejects_unknown_fields(tmp_path):
    client = TestClient(create_app(settings=Settings(workspace=tmp_path)))
    requirements = {"quantity": "impedance_ohm", "value": 50, "min_gap_um": 8}
    response = client.post("/layout/from-goal", json={"requirements": requirements,
                                                    "execute_solver": False})
    assert response.status_code == 200
    assert response.json()["intent"]["constraints"]["min_gap_um"] == 8
    assert response.json()["verification"]["status"] == "pass"
    requirements["unknown_constraint"] = 1
    assert client.post("/layout/from-goal", json={"requirements": requirements}).status_code == 422


@pytest.mark.parametrize("tolerance,expected_status", [(5.0, "pass"), (1e-12, "fail")])
def test_goal_cli_and_exported_reports_share_final_target_verdict(
    tmp_path, capsys, tolerance, expected_status
):
    # The length is snapped to the generator's precision. A deliberately tighter
    # target exposes the failure path without pretending to improve accuracy.
    source = tmp_path / "requirements.json"
    source.write_text(json.dumps({"quantity": "quarter_wave_frequency_ghz", "value": 6,
                                  "tolerance_percent": tolerance}))
    out = tmp_path / "layout"
    code = main(["design", str(source), "--out", str(out), "--no-solver"])
    response = json.loads(capsys.readouterr().out)
    verification = json.loads((out / "verification.json").read_text())
    target_verification = json.loads((out / "requirements_verification.json").read_text())
    review = json.loads((out / "design_review.json").read_text())
    assert code == (0 if expected_status == "pass" else 1)
    assert response["verification"]["status"] == expected_status
    assert verification == target_verification == review["verification"]
    assert verification["status"] == expected_status
    assert verification["target_basis"] == "analytical estimate"
    assert review["layout_requirements_passed"] == (expected_status == "pass")
    report = (out / "report.md").read_text()
    assert f"Geometry verification: **{expected_status.upper()}**" in report
    assert "requirements_target" in report
    assert "SIMULATION_INPUT_PREPARED" in report
