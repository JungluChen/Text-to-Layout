"""FastAPI plugin server tests (structured JSON contract)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from textlayout.backend import Settings, create_app

ROOT = Path(__file__).parents[2]

IDC_DSL = {
    "component": "IDC",
    "parameters": {
        "finger_pairs": 12,
        "finger_width_um": 4,
        "gap_um": 2,
        "overlap_um": 200,
        "bus_width_um": 25,
        "metal_layer": "M1",
    },
    "rules": {"min_width_um": 2, "min_gap_um": 2},
    "outputs": {"gds": True, "svg": True, "json": True},
}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(settings=Settings(workspace=tmp_path))
    return TestClient(app)


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "IDC" in body["components"]
    assert {"CPW", "SpiralInductor", "QuarterWaveResonator", "SQUID"} <= set(body["components"])
    assert "gds" in body["formats"]


def test_generate_returns_structured_json(client: TestClient) -> None:
    resp = client.post("/layout/generate", json=IDC_DSL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pass"
    assert body["verification"]["status"] == "pass"
    assert "json" in body["artifacts"] and "svg" in body["artifacts"]
    assert "gds" in body["files"]
    assert Path(body["files"]["gds"]).exists()


def test_verify_fail_path(client: TestClient) -> None:
    bad = {**IDC_DSL, "parameters": {**IDC_DSL["parameters"], "gap_um": 1.0}}
    resp = client.post("/layout/verify", json=bad)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "fail"
    assert any(c["name"] == "minimum_gap" and c["status"] == "fail" for c in body["checks"])


def test_invalid_parameters_returns_400(client: TestClient) -> None:
    bad = {**IDC_DSL, "parameters": {**IDC_DSL["parameters"], "finger_width_um": -1}}
    resp = client.post("/layout/generate", json=bad)
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "InvalidParametersError"


def test_unknown_component_returns_400(client: TestClient) -> None:
    resp = client.post("/layout/generate", json={"component": "Nope", "parameters": {}})
    assert resp.status_code == 400
    assert resp.json()["error"] == "UnknownComponentError"


def test_preview_returns_svg(client: TestClient) -> None:
    resp = client.post("/layout/preview", json=IDC_DSL)
    assert resp.status_code == 200
    assert resp.json()["svg"].startswith("<svg")


def test_export_gds(client: TestClient) -> None:
    resp = client.post("/layout/export", params={"format": "gds"}, json=IDC_DSL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["format"] == "gds"
    assert body["bytes"] > 0
    assert Path(body["file"]).exists()


def test_report_includes_simulation_steps(client: TestClient) -> None:
    resp = client.post("/layout/report", json=IDC_DSL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["simulation_next_steps"][0]["stage"] == "prepare"
    assert body["verification"]["status"] == "pass"
    assert body["evidence"]["references"]


def test_research_returns_equations_and_references(client: TestClient) -> None:
    resp = client.post("/layout/research", json=IDC_DSL)
    assert resp.status_code == 200
    evidence = resp.json()["evidence"]
    assert evidence["equations"]
    assert evidence["references"]
    assert evidence["simulation_recommendation"]


def test_benchmark_returns_complete_packet(client: TestClient) -> None:
    resp = client.post("/layout/benchmark", json=IDC_DSL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pass"
    assert {
        "gds",
        "svg",
        "json",
        "verification",
        "analytical_estimate",
        "simulation_plan",
        "evidence",
        "report",
    } <= set(body["files"])
    assert "No EM solver was executed" in body["report_markdown"]
    assert body["simulation"]["readiness_level"] == 2
    assert body["simulation"]["status"] == "input_files_prepared"


def test_simulate_prepares_open_source_idc_inputs(client: TestClient) -> None:
    resp = client.post("/layout/simulate", json=IDC_DSL)
    assert resp.status_code == 200
    simulation = resp.json()["simulation"]
    assert simulation["status"] == "input_files_prepared"
    assert simulation["readiness_level"] == 2
    assert Path(simulation["artifacts"]["panel_file"]).is_file()
    assert Path(simulation["artifacts"]["list_file"]).is_file()


def test_simulate_prepares_cpw_openems_manifest(client: TestClient) -> None:
    cpw = (ROOT / "examples/benchmarks/02_cpw_50ohm/layout.json").read_text(encoding="utf-8")
    resp = client.post(
        "/layout/simulate", content=cpw, headers={"content-type": "application/json"}
    )
    assert resp.status_code == 200
    simulation = resp.json()["simulation"]
    assert simulation["solver"] == "openEMS"
    assert simulation["readiness_level"] == 2
    assert Path(simulation["artifacts"]["model"]).is_file()
