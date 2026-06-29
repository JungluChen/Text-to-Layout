"""FastAPI plugin server tests (structured JSON contract)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from textlayout.backend import Settings, create_app

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
    assert body["simulation_next_steps"][0]["stage"] == "import"
    assert body["verification"]["status"] == "pass"
