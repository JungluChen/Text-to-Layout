from __future__ import annotations

from text_to_gds.em_solvers import (
    get_em_solver,
    list_em_solvers,
    recommend_em_solver,
)


def test_list_em_solvers_reports_all_backends():
    solvers = {entry["name"] for entry in list_em_solvers()}
    assert solvers == {"openEMS", "Palace", "Elmer", "MEEP"}
    assert get_em_solver("meep").open_source and get_em_solver("meep").method == "fdtd"
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


def test_routing_is_open_source_only():
    ranking = recommend_em_solver({"info": {"device_type": "cpw_resonator"}})["ranking"]
    assert {entry["solver"] for entry in ranking} <= {"openEMS", "Palace", "Elmer", "MEEP"}
    assert all(entry["open_source"] for entry in ranking)
    assert all(entry["role"] == "primary" for entry in ranking)
