from __future__ import annotations

from text_to_gds.em_solvers import (
    get_em_solver,
    list_em_solvers,
    recommend_em_solver,
)


def test_list_em_solvers_reports_all_backends():
    solvers = {entry["name"] for entry in list_em_solvers()}
    assert solvers == {"openEMS", "HFSS", "Sonnet", "Palace", "Elmer"}
    hfss = get_em_solver("hfss")
    assert hfss.license_required and not hfss.open_source
    assert get_em_solver("openems").open_source
    assert get_em_solver("palace").open_source and not get_em_solver("palace").license_required
    assert get_em_solver("elmer").method == "fem_electrostatic"


def test_routing_is_open_source_first():
    planar = recommend_em_solver({"info": {"device_type": "cpw_resonator"}})
    assert planar["geometry_class"] == "planar"
    assert planar["recommended"] == "openEMS"
    assert planar["recommended_open_source"] is True

    package = recommend_em_solver({"info": {"device_type": "package_bondwire_model"}})
    assert package["geometry_class"] == "volumetric"
    assert package["recommended"] == "Palace"

    lumped = recommend_em_solver({"pcell": "lumped_element_jpa_seed"})
    assert lumped["recommended"] == "openEMS"


def test_commercial_solvers_are_validation_only_and_rank_below_open():
    ranking = recommend_em_solver({"info": {"device_type": "cpw_resonator"}})["ranking"]
    roles = {entry["solver"]: entry["role"] for entry in ranking}
    assert roles["HFSS"] == "validation_only"
    assert roles["Sonnet"] == "validation_only"
    assert roles["openEMS"] == "primary"
    # Every open backend ranks strictly above every commercial backend.
    open_scores = [e["score"] for e in ranking if e["open_source"]]
    commercial_scores = [e["score"] for e in ranking if not e["open_source"]]
    assert min(open_scores) > max(commercial_scores)


def test_sonnet_solver_prepare_writes_handoff(tmp_path):
    gds = tmp_path / "device.gds"
    gds.write_bytes(b"fixture")
    result = get_em_solver("Sonnet").prepare(gds, output_stem=tmp_path / "device")
    assert result["status"] == "prepared"
    assert (tmp_path / "device.sonnet.m").exists()
