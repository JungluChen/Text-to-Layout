from __future__ import annotations

import json

from text_to_gds.pcells import manhattan_josephson_junction
from text_to_gds.server import compile_layout, run_drc, run_simulation
from text_to_gds.simulation import critical_current_ua, josephson_inductance_ph


def test_manhattan_josephson_junction_writes_gds(tmp_path):
    component = manhattan_josephson_junction()
    output = tmp_path / "jj.gds"

    component.write_gds(output)

    assert output.exists()
    assert component.info["junction_area_um2"] == 0.22 * 0.22
    assert len(component.ports) == 4


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
