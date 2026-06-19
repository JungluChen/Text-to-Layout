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


def test_routing_prefers_sonnet_for_planar_and_hfss_for_packaging():
    planar = recommend_em_solver({"info": {"device_type": "cpw_resonator"}})
    assert planar["geometry_class"] == "planar"
    assert planar["recommended"] == "Sonnet"

    package = recommend_em_solver({"info": {"device_type": "package_bondwire_model"}})
    assert package["geometry_class"] == "volumetric"
    assert package["recommended"] == "HFSS"

    lumped = recommend_em_solver({"pcell": "lumped_element_jpa_seed"})
    assert lumped["recommended"] == "openEMS"


def test_sonnet_solver_prepare_writes_handoff(tmp_path):
    gds = tmp_path / "device.gds"
    gds.write_bytes(b"fixture")
    result = get_em_solver("Sonnet").prepare(gds, output_stem=tmp_path / "device")
    assert result["status"] == "prepared"
    assert (tmp_path / "device.sonnet.m").exists()
