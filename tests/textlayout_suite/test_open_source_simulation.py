"""Open-source simulation preparation and truthful failure tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from textlayout import build_default_workflow
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation import prepare_idc_fastercap, run_fastercap

ROOT = Path(__file__).parents[2]
LAYOUT = ROOT / "examples" / "benchmarks" / "01_idc_0p6pf" / "layout.json"


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


def test_idc_fastercap_input_is_real_panel_and_list_format(tmp_path: Path) -> None:
    prepared = _prepared(tmp_path)
    assert prepared.status == "input_files_prepared"
    assert prepared.readiness_level == 2
    panel = Path(prepared.artifacts["panel_file"]).read_text(encoding="ascii")
    list_file = Path(prepared.artifacts["list_file"]).read_text(encoding="ascii")
    assert panel.startswith("0 ")
    assert "Q P1 " in panel and "Q P2 " in panel
    assert list_file.splitlines()[-1].startswith("C idc.qui ")
    manifest = json.loads(Path(prepared.artifacts["manifest"]).read_text(encoding="utf-8"))
    assert manifest["status"] == "input_files_prepared"
    assert manifest["model_assumptions"]


def test_missing_solver_is_skipped_without_result(tmp_path: Path) -> None:
    result = run_fastercap(_prepared(tmp_path), executable="solver-that-does-not-exist")
    assert result.status == "skipped"
    assert result.readiness_level == 2
    assert "result" not in result.artifacts


def test_runner_script_fails_gracefully_when_solver_missing(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "simulation/idc_fastercap/run_fastercap.py",
            str(LAYOUT),
            "--out",
            str(tmp_path),
            "--executable",
            "solver-that-does-not-exist",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["status"] == "skipped"
    assert not (tmp_path / "simulation_result.json").exists()
