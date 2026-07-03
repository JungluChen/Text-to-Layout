"""LangGraph pipeline: trace artifact, readback artifact, and the retune loop."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from textlayout import build_from_text_workflow
from textlayout.errors import PromptParseError
from textlayout.workflow.state import MAX_SOLVER_ITERATIONS

DEMO_PROMPT = "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap"

ROOT = Path(__file__).resolve().parents[2]
FAKE_SOLVER = ROOT / "tests" / "fixtures" / "fake_fastercap.py"

EXPECTED_NODES = [
    "ParsePrompt",
    "ValidateIntent",
    "BuildLayoutDSL",
    "OptimizeParameters",
    "GenerateGeometry",
    "ExportArtifacts",
    "KLayoutReadback",
    "GeometryVerification",
    "PrepareFasterCap",
    "RunFasterCapIfAvailable",
    "ParseSolverResult",
    "CompareTarget",
    "RunCircuitChecks",
    "GenerateReport",
    "UpdateShowcaseMetadata",
]


def test_workflow_trace_records_every_node(tmp_path: Path) -> None:
    workflow = build_from_text_workflow()
    result = workflow.run(DEMO_PROMPT, tmp_path / "run", execute_solver=False)
    trace_path = tmp_path / "run" / "workflow_trace.json"
    assert trace_path.is_file()
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["schema"] == "textlayout.workflow-trace.v1"
    assert trace["orchestrator"] == "langgraph"
    executed = [entry["node"] for entry in trace["nodes"]]
    for name in EXPECTED_NODES:
        assert name in executed, f"node {name} missing from trace"
    for entry in trace["nodes"]:
        assert entry["status"] == "ok"
        assert entry["start_time"] <= entry["end_time"]
        assert "input_summary" in entry and "output_summary" in entry
    assert "workflow_trace" in result.files


def test_workflow_writes_klayout_readback(tmp_path: Path) -> None:
    workflow = build_from_text_workflow()
    workflow.run(DEMO_PROMPT, tmp_path / "run", execute_solver=False)
    readback = json.loads(
        (tmp_path / "run" / "klayout_readback.json").read_text(encoding="utf-8")
    )
    assert readback["schema"] == "textlayout.klayout-readback.v1"
    assert readback["status"] == "pass"
    assert readback["polygon_count"] > 0
    check_names = {check["name"] for check in readback["checks"]}
    assert {"top_cell_exists", "bbox_non_empty", "expected_layers_present"} <= check_names


def test_trace_records_error_node_for_bad_prompt(tmp_path: Path) -> None:
    workflow = build_from_text_workflow()
    with pytest.raises(PromptParseError):
        workflow.run("Draw something nice", tmp_path / "bad")
    trace = json.loads((tmp_path / "bad" / "workflow_trace.json").read_text(encoding="utf-8"))
    assert trace["nodes"], "trace must exist even for failed runs"
    first = trace["nodes"][0]
    assert first["node"] == "ParsePrompt"
    assert first["status"] == "error"
    assert first["errors"]


@pytest.mark.skipif(sys.platform not in {"win32", "linux", "darwin"}, reason="needs python")
def test_solver_loop_is_bounded_and_recorded(tmp_path: Path, monkeypatch) -> None:
    # The fake solver always reports 0.652 pF against a 0.6 pF target, so the
    # loop can never converge — it must stop at the iteration budget.
    monkeypatch.setenv("FAKE_FASTERCAP_MUTUAL_PF", "0.652")
    workflow = build_from_text_workflow()
    result = workflow.run(DEMO_PROMPT, tmp_path / "loop", solver_executable=str(FAKE_SOLVER))
    assert result.optimization is not None
    iterations = result.optimization.solver_iterations
    assert 1 <= len(iterations) <= MAX_SOLVER_ITERATIONS
    assert all(entry["solver_status"] == "executed" for entry in iterations)
    trace = json.loads((tmp_path / "loop" / "workflow_trace.json").read_text(encoding="utf-8"))
    generate_runs = sum(1 for e in trace["nodes"] if e["node"] == "GenerateGeometry")
    assert generate_runs == len(iterations)
    assert result.evidence.status.value in {"SIMULATION_EXECUTED", "PHYSICS_VERIFIED"}


def test_converging_fake_solver_reaches_physics_verified(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_FASTERCAP_MUTUAL_PF", "0.600")
    workflow = build_from_text_workflow()
    result = workflow.run(DEMO_PROMPT, tmp_path / "run", solver_executable=str(FAKE_SOLVER))
    assert result.evidence.status.value == "PHYSICS_VERIFIED"
    for output in result.evidence.output_files:
        assert Path(output).is_file() and Path(output).stat().st_size > 0
