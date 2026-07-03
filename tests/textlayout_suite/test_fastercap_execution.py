"""FasterCap execution and evidence gates without requiring the real solver."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from textlayout import build_default_workflow
from textlayout.cli import main as textlayout_main
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation import prepare_idc_fastercap, run_fastercap
from textlayout.simulation.fastercap import _find_solver

ROOT = Path(__file__).resolve().parents[2]
LAYOUT = ROOT / "examples" / "benchmarks" / "01_idc_0p6pf" / "layout.json"
FAKE_SOLVER = ROOT / "tests" / "fixtures" / "fake_fastercap.py"


def _prepared(tmp_path: Path):
    spec = LayoutSpec.model_validate_json(LAYOUT.read_text(encoding="utf-8"))
    workflow = build_default_workflow()
    generated = workflow.run(spec, formats=())
    assert generated.report.passed
    return prepare_idc_fastercap(
        spec,
        generated.geometry,
        workflow.technology(spec.technology),
        tmp_path,
    )


def _payload(result) -> dict[str, object]:
    path = Path(result.artifacts["result"])
    assert path.is_file() and path.stat().st_size > 0
    return json.loads(path.read_text(encoding="utf-8"))


def test_solver_absent_writes_skipped_evidence(tmp_path: Path) -> None:
    result = run_fastercap(
        _prepared(tmp_path),
        executable="definitely-missing-fastercap-executable",
        target_capacitance_pf=0.6,
        tolerance_pct=5.0,
    )
    payload = _payload(result)
    assert result.status == "skipped"
    assert payload["solver_executed"] is False
    assert payload["physics_verified"] is False
    assert payload["prepared_inputs"] is True


def test_solver_discovery_honors_explicit_environment_and_tools_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _find_solver(str(FAKE_SOLVER)) == str(FAKE_SOLVER)
    monkeypatch.setenv("TEXTLAYOUT_FASTERCAP", str(FAKE_SOLVER))
    assert _find_solver(None) == str(FAKE_SOLVER)

    monkeypatch.delenv("TEXTLAYOUT_FASTERCAP")
    local_solver = tmp_path / "FasterCap" / "bin" / "FasterCap"
    local_solver.parent.mkdir(parents=True)
    local_solver.write_text("fixture", encoding="ascii")
    monkeypatch.setenv("TEXTLAYOUT_TOOLS_DIR", str(tmp_path))
    assert _find_solver(None) == str(local_solver)


def test_solver_present_within_tolerance_is_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_FASTERCAP_MUTUAL_PF", "0.600")
    result = run_fastercap(
        _prepared(tmp_path),
        executable=str(FAKE_SOLVER),
        target_capacitance_pf=0.6,
        tolerance_pct=5.0,
    )
    payload = _payload(result)
    assert result.status == "executed"
    assert payload["solver_executed"] is True
    assert payload["capacitance_matrix_parsed"] is True
    assert payload["target_compared"] is True
    assert payload["mutual_capacitance_pf"] == pytest.approx(0.6)
    assert payload["target_comparison"]["within_tolerance"] is True
    assert payload["physics_verified"] is True


def test_solver_present_outside_tolerance_remains_executed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_FASTERCAP_MUTUAL_PF", "0.652")
    result = run_fastercap(
        _prepared(tmp_path),
        executable=str(FAKE_SOLVER),
        target_capacitance_pf=0.6,
        tolerance_pct=5.0,
    )
    payload = _payload(result)
    assert result.status == "executed"
    assert payload["target_comparison"]["within_tolerance"] is False
    assert payload["physics_verified"] is False


def test_solver_malformed_output_fails_parser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_FASTERCAP_MODE", "malformed")
    result = run_fastercap(
        _prepared(tmp_path),
        executable=str(FAKE_SOLVER),
        target_capacitance_pf=0.6,
    )
    payload = _payload(result)
    assert result.status == "failed"
    assert payload["physics_verified"] is False
    assert "parser failed" in result.reason.lower()


def test_solver_nonzero_saves_stdout_and_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_FASTERCAP_MODE", "nonzero")
    result = run_fastercap(
        _prepared(tmp_path),
        executable=str(FAKE_SOLVER),
        target_capacitance_pf=0.6,
    )
    payload = _payload(result)
    assert result.status == "failed"
    assert payload["return_code"] == 1
    assert payload["physics_verified"] is False
    for key in ("solver_stdout", "solver_stderr"):
        artifact = Path(payload["artifacts"][key])
        assert artifact.is_file() and artifact.stat().st_size > 0


def test_cli_extracts_layout_target_and_returns_zero_outside_tolerance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_FASTERCAP_MUTUAL_PF", "0.652")
    out = tmp_path / "cli"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "simulation" / "idc_fastercap" / "run_fastercap.py"),
            str(LAYOUT),
            "--out",
            str(out),
            "--executable",
            str(FAKE_SOLVER),
            "--tolerance-pct",
            "5",
        ],
        cwd=ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads((out / "simulation_result.json").read_text(encoding="utf-8"))
    assert payload["target_comparison"]["target"] == pytest.approx(0.6)
    assert payload["target_comparison"]["within_tolerance"] is False


def test_prompt_to_idc_solver_evidence_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FAKE_FASTERCAP_MUTUAL_PF", "0.600")
    out = tmp_path / "idc_demo"
    code = textlayout_main(
        [
            "prompt",
            "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap",
            "--out",
            str(out),
            "--executable",
            str(FAKE_SOLVER),
        ]
    )
    assert code == 0, capsys.readouterr().out
    for name in (
        "intent.json",
        "layout.json",
        "output.gds",
        "output.svg",
        "verification.json",
        "simulation.json",
        "optimization.json",
        "report.md",
    ):
        artifact = out / name
        assert artifact.is_file() and artifact.stat().st_size > 0
    simulation = json.loads((out / "simulation.json").read_text(encoding="utf-8"))
    assert simulation["solver_executed"] is True
    assert simulation["mutual_capacitance_pf"] == pytest.approx(0.6)
    assert simulation["target_comparison"]["within_tolerance"] is True
    assert simulation["physics_verified"] is True
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "FasterCap" in report
    assert "Solver executed: **yes**" in report
    assert "not fabrication-ready" in report
