from __future__ import annotations

import math

import numpy as np
import pytest

from text_to_gds.em_extensions import lumped_element_fit, mesh_convergence_analysis, vector_fit
from text_to_gds.fabrication import (
    predict_wafer_ic,
    record_junction_measurement,
    record_oxidation_recipe,
    record_wafer_run,
)
from text_to_gds.improvements import call_improvement, list_improvements, validate_improvement_registry
from text_to_gds.measurement_extensions import extract_bandwidth, extract_ip3, squeezing_analysis
from text_to_gds.physics_extensions import (
    dielectric_loss_participation,
    optimize_cpw_impedance,
    surface_impedance_model,
)
from text_to_gds.platform_extensions import (
    authorize,
    index_record,
    search_records,
    similarity_search,
)
from text_to_gds.quantum_extensions import extract_hamiltonian, qubit_lifetime_prediction
from text_to_gds.verification import (
    extract_circuit_from_gds,
    extract_equivalent_circuit,
    generate_spice_netlist,
    run_superconducting_lvs,
)


def _sidecar() -> dict:
    return {
        "pcell": "manhattan_josephson_junction",
        "ports": [{"name": "west"}, {"name": "east"}],
        "info": {"junction_area_um2": 0.04},
    }


def test_all_157_improvements_are_registered_and_resolvable():
    registry = list_improvements()
    assert registry["count"] == 157
    assert [feature["id"] for feature in registry["features"]] == list(range(1, 158))
    assert validate_improvement_registry() == {
        "passed": True,
        "missing": [],
        "unresolved": [],
        "count": 157,
    }
    assert call_improvement(21)["Nb"]["tc_k"] == 9.2


def test_extraction_spice_and_real_topology_lvs():
    circuit = extract_equivalent_circuit(_sidecar())
    assert circuit["elements"][0]["kind"] == "josephson_junction"
    spice = generate_spice_netlist(circuit)
    assert ".MODEL jjmod JJ" in spice
    schematic = {"elements": [{"kind": "josephson_junction", "nodes": ["west", "east"]}]}
    assert run_superconducting_lvs(circuit, schematic)["passed"] is True
    schematic["elements"].append({"kind": "capacitor", "nodes": ["west", "east"]})
    assert run_superconducting_lvs(circuit, schematic)["passed"] is False


def test_polygon_gds_extraction_finds_junction(tmp_path):
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.dbu = 0.001
    top = layout.create_cell("TOP")
    top.shapes(layout.layer(3, 0)).insert(kdb.DBox(0.0, 0.0, 1.0, 1.0))
    top.shapes(layout.layer(4, 0)).insert(kdb.DBox(0.4, 0.4, 0.6, 0.6))
    top.shapes(layout.layer(5, 0)).insert(kdb.DBox(0.3, 0.3, 0.7, 0.7))
    path = tmp_path / "junction.gds"
    layout.write(str(path))
    circuit = extract_circuit_from_gds(path)
    assert circuit["polygon_connectivity_complete"] is True
    assert circuit["elements"][0]["kind"] == "josephson_junction"
    assert circuit["elements"][0]["parameters"]["area_um2"] == pytest.approx(0.04)


def test_fabrication_history_and_position_prediction(tmp_path):
    database = tmp_path / "fabrication.sqlite"
    record_wafer_run(database, wafer_id="W1", process_id="ncu", process_version="1.0.0")
    record_oxidation_recipe(database, recipe_id="OX1", pressure_mbar=10.0, time_s=600.0, temperature_c=23.0)
    for index, (x, y) in enumerate(((-5, -5), (-5, 5), (5, -5), (5, 5), (0, 0))):
        jc = 2.0 + 0.01 * x - 0.005 * y
        record_junction_measurement(database, wafer_id="W1", device_id=f"J{index}", x_mm=x, y_mm=y, area_um2=0.05, ic_ua=0.05 * jc)
    prediction = predict_wafer_ic(database, wafer_id="W1", x_mm=2.0, y_mm=-2.0, area_um2=0.05)
    assert prediction["sample_count"] == 5
    assert prediction["predicted_jc_ua_per_um2"] == pytest.approx(2.03, rel=1e-6)


def test_physics_and_em_extensions():
    impedance = surface_impedance_model(frequency_hz=6e9, surface_resistance_ohm=1e-6, kinetic_inductance_h_per_square=1e-12)
    assert impedance["reactance_ohm_per_square"] == pytest.approx(2 * math.pi * 6e9 * 1e-12)
    loss = dielectric_loss_participation([{"electric_energy_j": 2.0, "loss_tangent": 1e-3}, {"electric_energy_j": 1.0, "loss_tangent": 2e-3}])
    assert loss["dielectric_limited_q"] == pytest.approx(750.0)
    cpw = optimize_cpw_impedance(target_ohm=50.0)
    assert abs(cpw["error_ohm"]) < 0.2

    convergence = mesh_convergence_analysis([{"mesh_size_um": 2.0, "frequency_ghz": 6.1}, {"mesh_size_um": 1.0, "frequency_ghz": 6.01}, {"mesh_size_um": 0.5, "frequency_ghz": 6.005}], tolerance_fraction=0.001)
    assert convergence["converged"] is True
    frequencies = np.linspace(4e9, 8e9, 41)
    impedance_values = 3.0 + 1j * (2 * np.pi * frequencies * 2e-9 - 1 / (2 * np.pi * frequencies * 1e-12))
    fitted = lumped_element_fit(frequencies.tolist(), impedance_values.tolist())
    assert fitted["resistance_ohm"] == pytest.approx(3.0)
    response = 1 / (1 + 1j * (frequencies - 6e9) / 1e8)
    assert vector_fit(frequencies.tolist(), response.tolist(), order=4)["stable"] is True


def test_quantum_measurement_and_searchable_records(tmp_path):
    hamiltonian = extract_hamiltonian(capacitance_f=80e-15, critical_current_a=30e-9)
    assert hamiltonian["transition_01_ghz"] > 0.0
    lifetime = qubit_lifetime_prediction({"dielectric": 100e-6, "purcell": 1e-3})
    assert lifetime["dominant_channel"] == "dielectric"
    bandwidth = extract_bandwidth([1, 2, 3, 4, 5], [0, 4, 5, 4, 0])
    assert bandwidth["bandwidth_hz"] == 2.0
    ip3 = extract_ip3([-30, -20, -10], [-10, 0, 10], [-60, -30, 0])
    assert ip3["iip3_dbm"] == pytest.approx(-5.0)
    squeezed = squeezing_analysis(np.linspace(-1, 1, 100).tolist(), (0.2 * np.linspace(-1, 1, 100)).tolist())
    assert squeezed["squeezing_db"] < 0.0

    database = tmp_path / "knowledge.sqlite"
    index_record(database, kind="device", record_key="A", payload={"frequency": 6.0}, text="JPA six GHz", vector=[1.0, 0.0])
    index_record(database, kind="device", record_key="B", payload={"frequency": 7.0}, text="TWPA seven GHz", vector=[0.0, 1.0])
    assert search_records(database, "JPA")[0]["record_key"] == "A"
    assert similarity_search(database, [0.9, 0.1])[0]["record_key"] == "A"
    assert authorize("viewer", "release") is False
    assert authorize("fabrication", "release") is True
