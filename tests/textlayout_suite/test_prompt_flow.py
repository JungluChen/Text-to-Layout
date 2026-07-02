"""Prompt compiler and IDC closed-loop acceptance tests."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from textlayout.backend import Settings, create_app
from textlayout.optimization import optimize_idc
from textlayout.prompt import parse_prompt
from textlayout.workflows import run_from_text


PROMPT = "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap"
REQUIRED = {
    "intent.json",
    "layout.json",
    "output.gds",
    "output.svg",
    "verification.json",
    "simulation.json",
    "report.md",
}


def test_parse_idc_prompt() -> None:
    intent = parse_prompt(PROMPT)
    assert intent.component == "IDC"
    assert intent.target_capacitance_pf == 0.6
    assert intent.frequency_ghz == 6.0
    assert intent.min_gap_um == 2.0
    assert intent.substrate_epsilon_r == 11.9


def test_parse_cpw_prompt() -> None:
    intent = parse_prompt("Create a 50 ohm CPW on silicon at 6 GHz")
    assert intent.component == "CPW"
    assert intent.target_impedance_ohm == 50.0


def test_idc_optimizer_converges_and_respects_rules() -> None:
    result = optimize_idc(
        target_capacitance_pf=0.6,
        frequency_ghz=6.0,
        substrate_epsilon_r=11.9,
        min_width_um=2.0,
        min_gap_um=2.0,
        tolerance_pct=1.0,
    )
    assert result.converged
    assert abs(result.error_pct) <= 1.0
    assert result.parameters["finger_width_um"] >= 2.0
    assert result.parameters["gap_um"] >= 2.0
    assert len(result.iterations) >= 2


def test_prompt_integration_and_solver_absent_contract(tmp_path: Path) -> None:
    result = run_from_text(PROMPT, tmp_path, solver_executable="definitely-not-a-solver")
    assert REQUIRED <= {path.name for path in tmp_path.iterdir()}
    assert result.verification["status"] == "pass"
    assert result.simulation["status"] == "SIMULATION_INPUT_PREPARED"
    assert result.simulation["solver_status"] == "SKIPPED_SOLVER_ABSENT"
    assert result.simulation["physics_verified"] is False
    assert "no physics verification was performed" in (tmp_path / "report.md").read_text(
        encoding="utf-8"
    )


def test_idc_prompt_golden_layout(tmp_path: Path) -> None:
    run_from_text(PROMPT, tmp_path, solver_executable="definitely-not-a-solver")
    actual = json.loads((tmp_path / "layout.json").read_text(encoding="utf-8"))
    expected = json.loads(
        (Path(__file__).parents[1] / "golden_layouts" / "expected_idc_prompt.json").read_text(
            encoding="utf-8"
        )
    )
    assert actual == expected


def test_from_text_api(tmp_path: Path) -> None:
    client = TestClient(create_app(settings=Settings(workspace=tmp_path)))
    response = client.post(
        "/layout/from-text",
        json={"prompt": PROMPT, "solver_executable": "definitely-not-a-solver"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["layout"]["component"] == "IDC"
    assert body["simulation"]["status"] == "SIMULATION_INPUT_PREPARED"
    assert all(Path(path).is_file() for path in body["files"].values())
