from __future__ import annotations

import json
from pathlib import Path

import pytest

from text_to_gds.device_optimizer import optimize_device
from text_to_gds.extracted_device import extract_device
from text_to_gds.jpa_physics import solve_jpa_model
from text_to_gds.microwave_validator import write_microwave_report
from text_to_gds.pcells import cpw_quarter_wave_resonator, manhattan_josephson_junction
from text_to_gds.solver_interfaces import FastCapSolver, OpenEMSSolver


def test_extract_device_jj_quantities_have_source_geometry(tmp_path: Path):
    component = manhattan_josephson_junction(junction_width=0.24, junction_height=0.20)
    gds = tmp_path / "jj.gds"
    component.write_gds(gds)
    out = tmp_path / "extracted_device.json"

    result = extract_device(
        gds,
        {"pcell": "manhattan_josephson_junction", "info": dict(component.info)},
        jc_ua_per_um2=2.0,
        specific_capacitance_ff_per_um2=60.0,
        output_path=out,
    )

    assert result["schema"] == "text-to-gds.extracted-device.v1"
    assert result["status"] == "ok"
    assert result["quantities"]["junction_area"]["value"] == pytest.approx(0.048)
    assert result["quantities"]["critical_current"]["formula"] == "Ic = Jc*A"
    assert result["quantities"]["josephson_inductance"]["method_label"] == "estimated"
    assert result["quantities"]["plasma_frequency"]["value"] > 0.0
    assert result["quantities"]["junction_area"]["source_geometry"]["layer_name"] == "JJ"
    assert json.loads(out.read_text(encoding="utf-8"))["device"] == "manhattan_josephson_junction"


def test_extract_device_cpw_per_length_values(tmp_path: Path):
    component = cpw_quarter_wave_resonator(target_frequency_ghz=6.0)
    gds = tmp_path / "cpw.gds"
    component.write_gds(gds)

    result = extract_device(gds, {"pcell": "cpw_quarter_wave_resonator", "info": dict(component.info)})

    quantities = result["quantities"]
    assert quantities["cpw_capacitance_per_meter"]["value"] > 0.0
    assert quantities["cpw_inductance_per_meter"]["value"] > 0.0
    assert 40.0 < quantities["cpw_impedance"]["value"] < 70.0
    assert quantities["cpw_quarter_wave_frequency"]["value"] == pytest.approx(6.0e9, rel=1e-6)


def test_solver_lifecycle_prepares_and_skips_missing_openems(tmp_path: Path):
    extraction = tmp_path / "extraction.json"
    extraction.write_text(
        json.dumps(
            {
                "schema": "text-to-gds.extraction.v1",
                "device": "cpw",
                "linear_circuit": {"resonance_frequency": 6.0e9},
                "solver_inputs": {"openems": {}},
            }
        ),
        encoding="utf-8",
    )

    solver = OpenEMSSolver(
        extraction,
        output_stem=tmp_path / "openems_case",
        openems_executable="definitely_missing_openems_for_test",
    )
    prepared = solver.prepare()
    assert prepared.status == "prepared"
    result = solver.execute()
    assert result["status"] == "skipped"
    assert "not found" in result["reason"]


def test_fastcap_prepare_writes_deck(tmp_path: Path):
    component = cpw_quarter_wave_resonator(target_frequency_ghz=6.0)
    gds = tmp_path / "cap.gds"
    component.write_gds(gds)

    solver = FastCapSolver(gds, output_stem=tmp_path / "cap_case")
    prepared = solver.prepare()

    assert prepared.status == "prepared"
    assert prepared.input_file is not None
    assert Path(prepared.input_file).exists()


def test_microwave_report_extracts_resonance_and_rejects_active_passive(tmp_path: Path):
    ts = tmp_path / "passive.s2p"
    ts.write_text(
        "# GHZ S DB R 50\n"
        "5.8 -20 0 -3 0 -3 0 -20 0\n"
        "6.0 -25 0 -20 0 -20 0 -25 0\n"
        "6.2 -20 0 -3 0 -3 0 -20 0\n",
        encoding="utf-8",
    )
    report = write_microwave_report(ts, tmp_path / "microwave_report.json")

    assert report["status"] == "ok"
    assert report["reciprocity"]["passed"] is True
    assert report["energy_conservation"]["passed"] is True
    assert report["resonance"]["f0_ghz"] == pytest.approx(6.0)

    active = tmp_path / "active.s2p"
    active.write_text("# GHZ S DB R 50\n6.0 -20 0 3 0 3 0 -20 0\n6.1 -20 0 2 0 2 0 -20 0\n", encoding="utf-8")
    passive_report = write_microwave_report(active, tmp_path / "active_passive.json", active_mode=False)
    active_report = write_microwave_report(active, tmp_path / "active_allowed.json", active_mode=True)
    assert passive_report["status"] == "failed"
    assert active_report["energy_conservation"]["passed"] is True


def test_jpa_physics_report_and_optimizer(tmp_path: Path):
    jpa = solve_jpa_model(
        lj_h=2.0e-9,
        capacitance_f=350e-15,
        kappa_hz=120e6,
        pump_strength_hz=45e6,
        report_path=tmp_path / "jpa_report.json",
    )
    assert jpa["status"] == "skipped"
    assert jpa["backend"] == "JosephsonCircuits.jl"
    assert jpa["values"] == {}
    assert (tmp_path / "jpa_report.json").exists()

    opt = optimize_device(
        "cpw_resonator",
        {"frequency_ghz": 6.0, "z0_ohm": 50.0},
        output_path=tmp_path / "optimization.json",
    )
    assert opt["schema"] == "text-to-gds.optimization-loop.v1"
    assert opt["solver_status"] == "skipped"
    assert opt["final_metrics"]["f0_ghz"] == pytest.approx(6.0)
