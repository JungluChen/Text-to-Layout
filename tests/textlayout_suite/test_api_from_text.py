"""Phase 9 category 4 — POST /layout/from-text API integration."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from textlayout.backend.app import create_app
from textlayout.backend.settings import Settings


def _client(tmp_path: Path) -> TestClient:
    app = create_app(settings=Settings(workspace=tmp_path))
    return TestClient(app)


def test_from_text_returns_artifacts_and_honest_status(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.post(
        "/layout/from-text",
        json={
            "prompt": "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap",
            "output_dir": str(tmp_path / "api_demo"),
            "execute_solver": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["component"] == "IDC"
    assert body["target"] == {"capacitance_pf": 0.6, "frequency_ghz": 6.0}
    assert body["simulation_status"] == "SIMULATION_INPUT_PREPARED"
    for kind in ("intent", "layout", "gds", "svg", "verification", "simulation", "report"):
        assert kind in body["artifacts"], f"missing artifact {kind}"
        assert Path(body["files"][kind]).is_file()
    assert body["optimization"]["converged"] is True
    # The evidence record embedded in the response obeys the contract.
    assert body["evidence"]["extracted_value"] is None
    intent = json.loads(Path(body["files"]["intent"]).read_text(encoding="utf-8"))
    assert intent["component"] == "IDC"


def test_from_text_malformed_prompt_is_http_400(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.post("/layout/from-text", json={"prompt": "Draw something nice"})
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "PromptParseError"
