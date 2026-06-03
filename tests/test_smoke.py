from __future__ import annotations

import json

from text_to_gds.pcells import cpw_straight, manhattan_josephson_junction, meander_inductor
from text_to_gds.server import (
    compile_layout,
    export_3d_preview,
    extract_layout,
    list_pcells,
    list_simulators,
    plan_ljpa,
    run_drc,
    run_simulation,
)
from text_to_gds.simulation import critical_current_ua, josephson_inductance_ph


def test_manhattan_josephson_junction_writes_gds(tmp_path):
    component = manhattan_josephson_junction()
    output = tmp_path / "jj.gds"

    component.write_gds(output)

    assert output.exists()
    assert component.info["junction_area_um2"] == 0.22 * 0.22
    assert len(component.ports) == 4


def test_passive_pcells_expose_performance_parameters(tmp_path):
    cpw = cpw_straight(length=120, trace_width=8, gap=4, angle_deg=45)
    assert cpw.info["device_type"] == "cpw_straight"
    assert cpw.info["angle_deg"] == 45
    assert cpw.info["gap_um"] == 4
    assert len(cpw.ports) == 2

    inductor = meander_inductor(num_turns=4, segment_length=15, trace_width=1, pitch=3)
    assert inductor.info["device_type"] == "meander_inductor"
    assert inductor.info["electrical_length_um"] == 4 * 15 + 3 * 3

    output = tmp_path / "passive.gds"
    inductor.write_gds(output)
    assert output.exists()


def test_mock_tool_chain_writes_sidecars(monkeypatch, tmp_path):
    monkeypatch.setattr("text_to_gds.server.ARTIFACT_ROOT", tmp_path)

    compiled = compile_layout(output_name="toolchain.gds")
    assert compiled["status"] == "compiled"
    assert (tmp_path / "toolchain.layout.png").exists()

    sidecar_path = tmp_path / "toolchain.sidecar.json"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["schema"] == "text-to-gds.sidecar.v0"
    assert sidecar["screenshot_path"] == compiled["screenshot_path"]
    assert sidecar["info"]["device_type"] == "manhattan_josephson_junction"
    assert sidecar["ports"][0]["layer"] == [3, 0]

    drc = run_drc(compiled["gds_path"])
    assert drc["status"] == "passed"
    assert drc["engine"] == "klayout_python_bbox"
    assert drc["checked_shapes"] == 3

    failing_drc = run_drc(compiled["gds_path"], min_width_um=0.3)
    assert failing_drc["status"] == "failed"
    assert failing_drc["violations"][0]["rule"] == "min_bbox_width"
    assert failing_drc["violations"][0]["layer"] == [4, 0]

    simulation = run_simulation(compiled["sidecar_path"], jc_ua_per_um2=2.0)
    assert simulation["critical_current_ua"] == sidecar["info"]["junction_area_um2"] * 2.0
    assert simulation["josephson_inductance_ph"] is not None

    extraction = extract_layout(compiled["sidecar_path"])
    assert extraction["schema"] == "text-to-gds.extraction-summary.v0"
    assert extraction["parameters"]["junction_area_um2"] == sidecar["info"]["junction_area_um2"]
    assert extraction["gds_shapes"]

    preview = export_3d_preview(compiled["gds_path"])
    assert preview["status"] == "previewed"
    assert (tmp_path / "toolchain.stack3d.html").exists()
    assert (tmp_path / "toolchain.stack3d.json").exists()

    josim = run_simulation(compiled["sidecar_path"], simulator="josim", jc_ua_per_um2=2.0)
    assert josim["adapter"] == "JoSIM"
    assert (tmp_path / "toolchain.sidecar.josim.cir").exists()


def test_registry_planner_and_adapter_metadata():
    pcells = list_pcells()
    assert "manhattan_josephson_junction" in pcells["pcells"]
    assert "cpw_straight" in pcells["pcells"]

    plan = plan_ljpa("Design a 5 Ghz LJPA with wilde bandwidth")
    assert plan["target"]["center_frequency_ghz"] == 5.0
    assert plan["target"]["bandwidth_mhz"] == 500.0
    assert any("material" in question.lower() for question in plan["clarifying_questions"])
    assert "JosephsonCircuits.jl" in {
        adapter["name"] for adapter in plan["simulation_adapters"]
    }

    simulators = list_simulators()
    assert {adapter["name"] for adapter in simulators["adapters"]} == {
        "JosephsonCircuits.jl",
        "JoSIM",
    }


def test_ideal_josephson_simulation_units():
    ic_ua = critical_current_ua(junction_area_um2=0.0484, jc_ua_per_um2=2.0)
    assert ic_ua == 0.0968

    lj_ph = josephson_inductance_ph(ic_ua)
    assert lj_ph is not None
    assert round(lj_ph, 6) == 3399.855149


def test_ideal_josephson_simulation_rejects_invalid_jc():
    try:
        critical_current_ua(junction_area_um2=0.0484, jc_ua_per_um2=0.0)
    except ValueError as error:
        assert "jc_ua_per_um2 must be positive" in str(error)
    else:
        raise AssertionError("expected ValueError")
