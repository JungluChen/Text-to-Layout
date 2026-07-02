"""Phase 9 categories 3, 5, 6, 7 — CLI integration, solver-absent/present, golden IDC.

The fake solver is a real executable script (platform-appropriate) so the
solver-present path exercises the true subprocess → stdout-capture → parser
chain, not a monkeypatched shortcut.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from textlayout import build_from_text_workflow
from textlayout.cli import main
from textlayout.evidence import EvidenceStatus

DEMO_PROMPT = "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap"

REQUIRED_FILES = (
    "intent.json",
    "layout.json",
    "output.gds",
    "output.svg",
    "verification.json",
    "simulation.json",
    "optimization.json",
    "report.md",
)


def _fake_solver(tmp_path: Path, *, mutual_pf: float) -> str:
    """Write an executable that prints a FasterCap-style capacitance matrix."""
    diag = mutual_pf + 0.3
    lines = [
        "CAPACITANCE MATRIX, picofarads",
        f"1 P1 {diag} -{mutual_pf}",
        f"2 P2 -{mutual_pf} {diag}",
    ]
    if sys.platform == "win32":
        script = tmp_path / "fake_fastercap.bat"
        script.write_text(
            "@echo off\n" + "\n".join(f"echo {line}" for line in lines) + "\n",
            encoding="ascii",
        )
    else:
        script = tmp_path / "fake_fastercap.sh"
        script.write_text(
            "#!/bin/sh\n" + "\n".join(f"echo '{line}'" for line in lines) + "\n",
            encoding="ascii",
        )
        os.chmod(script, 0o755)
    return str(script)


def test_cli_prompt_produces_all_required_files(tmp_path: Path, capsys) -> None:
    out = tmp_path / "idc_demo"
    code = main(["prompt", DEMO_PROMPT, "--out", str(out), "--no-solver"])
    assert code == 0
    for name in REQUIRED_FILES:
        path = out / name
        assert path.is_file() and path.stat().st_size > 0, f"missing {name}"
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["simulation_status"] == "SIMULATION_INPUT_PREPARED"


def test_cli_malformed_prompt_fails_gracefully(tmp_path: Path, capsys) -> None:
    code = main(["prompt", "Draw something nice", "--out", str(tmp_path / "x")])
    assert code == 1
    err = json.loads(capsys.readouterr().err)
    assert err["error"] == "PromptParseError"


def test_solver_absent_is_never_physics_verified(tmp_path: Path) -> None:
    workflow = build_from_text_workflow()
    result = workflow.run(
        DEMO_PROMPT,
        tmp_path / "no_solver",
        solver_executable="solver-that-does-not-exist",
    )
    assert result.evidence.status is EvidenceStatus.SKIPPED_SOLVER_ABSENT
    assert result.evidence.extracted_value is None
    report = (tmp_path / "no_solver" / "report.md").read_text(encoding="utf-8")
    assert "SKIPPED_SOLVER_ABSENT" in report
    assert "no physics verification was performed" in report
    assert "PHYSICS_VERIFIED" not in report


def test_solver_present_within_tolerance_is_physics_verified(tmp_path: Path) -> None:
    fake = _fake_solver(tmp_path, mutual_pf=0.598)
    workflow = build_from_text_workflow()
    result = workflow.run(DEMO_PROMPT, tmp_path / "run", solver_executable=fake)
    assert result.evidence.status is EvidenceStatus.PHYSICS_VERIFIED
    assert result.evidence.extracted_value == pytest.approx(0.598)
    assert result.evidence.error_percent is not None
    assert result.evidence.error_percent <= 5.0
    # The claim is backed by a real solver-owned output file.
    for output in result.evidence.output_files:
        assert Path(output).is_file() and Path(output).stat().st_size > 0
    simulation = json.loads((tmp_path / "run" / "simulation.json").read_text(encoding="utf-8"))
    assert simulation["evidence"][0]["status"] == "PHYSICS_VERIFIED"


def test_solver_present_out_of_tolerance_is_executed_not_verified(tmp_path: Path) -> None:
    fake = _fake_solver(tmp_path, mutual_pf=0.75)  # 25% off target
    workflow = build_from_text_workflow()
    result = workflow.run(DEMO_PROMPT, tmp_path / "run", solver_executable=fake)
    assert result.evidence.status is EvidenceStatus.SIMULATION_EXECUTED
    report = (tmp_path / "run" / "report.md").read_text(encoding="utf-8")
    assert "not physics verified" in report.lower()


def test_golden_idc_benchmark_is_stable_and_honest(tmp_path: Path) -> None:
    """Golden IDC: stable DSL, passing verification, no fake solver claims."""
    workflow = build_from_text_workflow()
    result = workflow.run(DEMO_PROMPT, tmp_path / "golden", execute_solver=False)

    layout = json.loads((tmp_path / "golden" / "layout.json").read_text(encoding="utf-8"))
    assert layout["component"] == "IDC"
    assert layout["target"] == {"capacitance_pf": 0.6, "frequency_ghz": 6.0}
    # Deterministic parser + optimizer: the tuned DSL must be reproducible.
    assert layout["parameters"] == {
        "finger_pairs": 20,
        "finger_width_um": 4.0,
        "gap_um": 2.0,
        "overlap_um": 237.362,
        "bus_width_um": 25.0,
        "metal_layer": "M1",
    }

    verification = json.loads(
        (tmp_path / "golden" / "verification.json").read_text(encoding="utf-8")
    )
    assert verification["status"] == "pass"

    assert result.optimization is not None and result.optimization.converged
    report = (tmp_path / "golden" / "report.md").read_text(encoding="utf-8")
    assert "SIMULATION_INPUT_PREPARED" in report
    assert "PHYSICS_VERIFIED" not in report
    assert "not fabrication-ready" in report
