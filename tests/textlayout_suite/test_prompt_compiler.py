"""End-to-end contracts for the deterministic text-to-layout boundary."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from textlayout.backend import Settings, create_app
from textlayout.errors import PromptCompilationError
from textlayout.workflows import compile_text, run_from_text


def test_compile_preserves_complete_idc_geometry() -> None:
    result = compile_text(
        "Create a 0.6 pF IDC with 22 finger pairs, 4 um width, "
        "2 um gap, and 250 um overlap."
    )

    assert result.optimization is None
    assert result.spec.component == "IDC"
    assert result.spec.parameters == {
        "finger_pairs": 22,
        "finger_width_um": 4.0,
        "gap_um": 2.0,
        "overlap_um": 250.0,
        "bus_width_um": 20.0,
        "metal_layer": "M1",
    }


def test_compile_supports_unicode_units_and_explicit_cpw_dimensions() -> None:
    result = compile_text(
        "Create a 50 Ω CPW on silicon with center width 12 µm, "
        "gap 7 µm, length 2.5 um, and ground width 60 um."
    )

    assert result.spec.target["impedance_ohm"] == 50.0
    assert result.spec.parameters["center_width_um"] == 12.0
    assert result.spec.parameters["gap_um"] == 7.0
    assert result.spec.parameters["length_um"] == 2.5
    assert result.spec.parameters["ground_width_um"] == 60.0


@pytest.mark.parametrize(
    ("prompt", "question"),
    [
        ("Create an IDC", "capacitance"),
        ("Create a resonator", "IDC or CPW"),
        ("Create an IDC connected to a CPW at 6 GHz", "Choose one component"),
    ],
)
def test_compile_rejects_missing_or_ambiguous_intent(prompt: str, question: str) -> None:
    with pytest.raises(PromptCompilationError) as caught:
        compile_text(prompt)
    assert question.lower() in str(caught.value.detail).lower()


def test_compile_api_returns_dsl_without_writing_files(tmp_path: Path) -> None:
    client = TestClient(create_app(settings=Settings(workspace=tmp_path)))
    response = client.post(
        "/layout/compile",
        json={"prompt": "Create a 50 ohm CPW on silicon."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["layout"]["component"] == "CPW"
    assert body["unresolved_questions"] == []
    assert not list(tmp_path.rglob("*"))


def test_compile_api_returns_structured_clarification(tmp_path: Path) -> None:
    client = TestClient(create_app(settings=Settings(workspace=tmp_path)))
    response = client.post("/layout/compile", json={"prompt": "Create an IDC"})

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "PromptCompilationError"
    assert body["detail"]["unresolved_questions"]


def test_from_text_writes_verified_geometry_and_honest_solver_status(tmp_path: Path) -> None:
    result = run_from_text(
        "Create a 0.6 pF IDC with 22 finger pairs, 4 um width, "
        "2 um gap, and 250 um overlap.",
        tmp_path,
        solver_executable="solver-that-does-not-exist",
    )

    assert result.verification["status"] == "pass"
    assert Path(result.files["gds"]).is_file()
    assert result.simulation["physics_verified"] is False
    assert result.simulation["solver_status"] == "SKIPPED_SOLVER_ABSENT"
