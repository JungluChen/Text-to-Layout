from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from text_to_gds.delivery_extensions import (
    claim_job,
    create_password_record,
    enqueue_job,
    latex_paper,
    verify_password,
)
from text_to_gds.foundry_extensions import (
    estimate_fabrication_cost,
    generate_project_template,
    migrate_process_geometry,
)
from text_to_gds.junction_physics import (
    ambegaokar_baratoff,
    junction_capacitance,
    temperature_dependent_ic,
)
from text_to_gds.layout_automation import floorplan_chip, route_cpw, route_microwave
from text_to_gds.next_improvements import (
    call_next_improvement,
    list_next_improvements,
    validate_next_improvement_registry,
)
from text_to_gds.pdk import load_pdk
from text_to_gds.research_automation import (
    lindblad_evolution,
    predict_em_surrogate,
    synthesize_filter,
    train_em_surrogate,
)
from text_to_gds.verification import commit_device_version, device_version_history


ROOT = Path(__file__).resolve().parents[1]


def test_all_146_next_improvements_are_callable():
    registry = list_next_improvements()
    assert registry["count"] == 146
    assert [item["id"] for item in registry["features"]] == list(range(1, 147))
    assert validate_next_improvement_registry() == {
        "passed": True,
        "count": 146,
        "missing": [],
        "unresolved": [],
    }
    assert "jpa" in call_next_improvement(2)["devices"]


def test_routing_floorplanning_and_project_templates():
    route = route_microwave((0.0, 0.0), (100.0, 0.0), obstacles=[[40.0, -10.0, 60.0, 10.0]], grid_um=10.0, clearance_um=0.0)
    assert route["length_um"] > 100.0
    assert route["bend_count"] >= 2
    cpw = route_cpw((0.0, 0.0), (100.0, 100.0), target_impedance_ohm=50.0, grid_um=10.0)
    assert abs(cpw["cross_section"]["error_ohm"]) < 0.2
    floorplan = floorplan_chip([{"name": "A", "width_um": 100, "height_um": 100}, {"name": "B", "width_um": 200, "height_um": 100}], chip_width_um=1000, chip_height_um=1000)
    assert len(floorplan["placements"]) == 2
    assert "project.yaml" in generate_project_template("jpa", name="test-jpa")


def test_process_migration_and_fabrication_cost():
    source = load_pdk(ROOT / "process" / "NCU_AlOx_2026.yaml")
    target = load_pdk(ROOT / "process" / "MIT_LL_SFQ.yaml")
    migration = migrate_process_geometry({"trace_width_um": 0.2, "junction_area_um2": 0.05}, source, target)
    assert migration["parameters"]["trace_width_um"] == 0.5
    assert migration["parameters"]["junction_area_um2"] < 0.05
    cost = estimate_fabrication_cost(wafer_count=2, mask_count=4, wafer_cost=1000, mask_cost=500, expected_yield=0.5, chips_per_wafer=100)
    assert cost["expected_good_chips"] == 100


def test_junction_models_have_physical_limits():
    ab = ambegaokar_baratoff(normal_resistance_ohm=10.0, temperature_k=0.02, critical_temperature_k=1.2)
    assert 0.0002 < ab["icrn_v"] < 0.0004
    temperature = temperature_dependent_ic(zero_temperature_ic_a=30e-9, temperatures_k=[0.02, 1.2], critical_temperature_k=1.2)
    assert temperature["critical_current_a"][0] > 0.0
    assert temperature["critical_current_a"][1] == 0.0
    capacitance = junction_capacitance(area_um2=0.05, barrier_thickness_nm=2.0, relative_permittivity=9.0)
    assert capacitance["total_f"] > 0.0


def test_em_surrogate_filter_and_lindblad_solver():
    samples = []
    for width in (1.0, 2.0, 3.0, 4.0, 5.0):
        samples.append({"parameters": {"width": width}, "metrics": {"frequency": 7.0 - 0.5 * width + 0.1 * width**2}})
    model = train_em_surrogate(samples, ["width"], ["frequency"])
    prediction = predict_em_surrogate(model, {"width": 2.5})
    assert prediction["frequency"] == pytest.approx(6.375, rel=1e-6)
    filter_model = synthesize_filter(kind="butterworth_lowpass", order=3, cutoff_hz=1e9)
    assert [element["kind"] for element in filter_model["elements"]] == ["inductor", "capacitor", "inductor"]

    collapse = [[0.0, math.sqrt(1.0)], [0.0, 0.0]]
    evolution = lindblad_evolution(hamiltonian=[[0.0, 0.0], [0.0, 0.0]], collapse_operators=[collapse], initial_density=[[0.0, 0.0], [0.0, 1.0]], times_s=np.linspace(0.0, 1.0, 101).tolist())
    final = evolution["density_matrices"][-1]
    assert final[1][1][0] == pytest.approx(math.exp(-1.0), rel=1e-5)


def test_job_queue_authentication_and_latex(tmp_path):
    database = tmp_path / "jobs.sqlite"
    low = enqueue_job(database, kind="em", payload={"id": "low"}, priority=1)
    high = enqueue_job(database, kind="em", payload={"id": "high"}, priority=10)
    assert low["job_id"] != high["job_id"]
    assert claim_job(database)["payload"]["id"] == "high"
    password = create_password_record("correct horse battery staple")
    assert verify_password("correct horse battery staple", password) is True
    assert verify_password("wrong", password) is False
    paper = latex_paper(title="JPA", authors=["A", "B"], abstract="Test", sections=[{"title": "Methods", "body": "Local methods."}], template="nature")
    assert "\\author{A \\and B}" in paper


def test_git_style_device_version_history(tmp_path):
    database = tmp_path / "versions.sqlite"
    first = commit_device_version(database, device_id="JPA-1", design={"frequency": 6.0}, message="initial")
    second = commit_device_version(database, device_id="JPA-1", design={"frequency": 6.1}, message="retuned", parent_hash=first["commit_hash"])
    history = device_version_history(database, "JPA-1")
    assert [item["commit_hash"] for item in history] == [first["commit_hash"], second["commit_hash"]]
    assert history[1]["parent_hash"] == first["commit_hash"]
