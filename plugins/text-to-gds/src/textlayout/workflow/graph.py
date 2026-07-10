"""LangGraph graph definition, tracing, and the public workflow runner.

Node topology (the solver retune loop is the only cycle)::

    ParsePrompt → ValidateIntent → BuildLayoutDSL → OptimizeParameters
      → GenerateGeometry → ExportArtifacts → KLayoutReadback
      → GeometryVerification → PrepareFasterCap → RunFasterCapIfAvailable
      → ParseSolverResult → CompareTarget
            ├─(out of tolerance, budget left)→ RetuneParameters → GenerateGeometry
            └─(otherwise)→ RunCircuitChecks → GenerateReport → UpdateShowcaseMetadata

Every node execution is timed and appended to ``workflow_trace.json`` with its
status, input/output summaries, warnings, and errors — the audit trail a
reviewer needs to see which stage produced which artifact.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from langgraph.graph import END, START, StateGraph

from textlayout.workflow.nodes import PromptPipeline, should_retune, summarize_state
from textlayout.workflow.state import LayoutWorkflowState
from textlayout.workflows.from_text import FromTextResult
from textlayout.workflows.generate import GenerateWorkflow

TRACE_SCHEMA = "textlayout.workflow-trace.v1"

#: (node name, PromptPipeline method name) in execution order.
_NODES: tuple[tuple[str, str], ...] = (
    ("ParsePrompt", "parse_prompt"),
    ("ValidateIntent", "validate_intent"),
    ("BuildLayoutDSL", "build_layout_dsl"),
    ("OptimizeParameters", "optimize_parameters"),
    ("GenerateGeometry", "generate_geometry"),
    ("ExportArtifacts", "export_artifacts"),
    ("KLayoutReadback", "klayout_readback"),
    ("GeometryVerification", "geometry_verification"),
    ("PrepareFasterCap", "prepare_fastercap"),
    ("RunFasterCapIfAvailable", "run_fastercap_if_available"),
    ("ParseSolverResult", "parse_solver_result"),
    ("CompareTarget", "compare_target"),
    ("RetuneParameters", "retune_parameters"),
    ("RunCircuitChecks", "run_circuit_checks"),
    ("GenerateReport", "generate_report"),
    ("UpdateShowcaseMetadata", "update_showcase_metadata"),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _traced(
    name: str,
    fn: Callable[[LayoutWorkflowState], dict[str, Any]],
    trace_log: list[dict[str, Any]],
) -> Callable[[LayoutWorkflowState], dict[str, Any]]:
    def wrapper(state: LayoutWorkflowState) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "node": name,
            "start_time": _now(),
            "input_summary": summarize_state(state),
            "warnings": [],
            "errors": [],
        }
        try:
            updates = fn(state) or {}
        except Exception as exc:
            entry["end_time"] = _now()
            entry["status"] = "error"
            entry["errors"] = [f"{type(exc).__name__}: {exc}"]
            entry["output_summary"] = {}
            trace_log.append(entry)
            raise
        entry["end_time"] = _now()
        entry["status"] = "ok"
        entry["output_summary"] = {"updated": sorted(updates)}
        new_warnings = updates.get("warnings")
        if isinstance(new_warnings, list) and len(new_warnings) > len(state.warnings):
            entry["warnings"] = new_warnings[len(state.warnings) :]
        trace_log.append(entry)
        updates["trace"] = state.trace + [dict(entry)]
        return updates

    return wrapper


def build_layout_graph(
    generate_workflow: GenerateWorkflow,
    trace_log: list[dict[str, Any]] | None = None,
) -> Any:
    """Compile the LangGraph pipeline around one deterministic core."""
    pipeline = PromptPipeline(generate_workflow)
    log: list[dict[str, Any]] = trace_log if trace_log is not None else []

    graph: StateGraph[LayoutWorkflowState] = StateGraph(LayoutWorkflowState)
    for node_name, method_name in _NODES:
        traced = _traced(node_name, getattr(pipeline, method_name), log)
        graph.add_node(node_name, cast(Any, traced))

    graph.add_edge(START, "ParsePrompt")
    linear = [
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
    ]
    for src, dst in zip(linear, linear[1:]):
        graph.add_edge(src, dst)
    graph.add_conditional_edges(
        "CompareTarget",
        lambda state: "RetuneParameters" if should_retune(state) else "RunCircuitChecks",
        {"RetuneParameters": "RetuneParameters", "RunCircuitChecks": "RunCircuitChecks"},
    )
    graph.add_edge("RetuneParameters", "GenerateGeometry")
    graph.add_edge("RunCircuitChecks", "GenerateReport")
    graph.add_edge("GenerateReport", "UpdateShowcaseMetadata")
    graph.add_edge("UpdateShowcaseMetadata", END)
    return graph.compile()


def write_trace(trace_log: list[dict[str, Any]], out: Path) -> str:
    path = out / "workflow_trace.json"
    payload = {
        "schema": TRACE_SCHEMA,
        "orchestrator": "langgraph",
        "generated_at": _now(),
        "nodes": trace_log,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return str(path)


def run_prompt_workflow(
    generate_workflow: GenerateWorkflow,
    prompt: str,
    output_dir: str | Path,
    *,
    tolerance_percent: float = 5.0,
    execute_solver: bool = True,
    solver_executable: str | None = None,
) -> FromTextResult:
    """Execute the full LangGraph pipeline and return the classic result object.

    ``workflow_trace.json`` is written even when a node fails, so a partial run
    still leaves an auditable record of where and why it stopped.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    trace_log: list[dict[str, Any]] = []
    app = build_layout_graph(generate_workflow, trace_log)
    initial = LayoutWorkflowState(
        prompt=prompt,
        output_dir=out,
        tolerance_percent=tolerance_percent,
        execute_solver=execute_solver,
        solver_executable=solver_executable,
    )
    try:
        final = app.invoke(initial, config={"recursion_limit": 200})
    finally:
        write_trace(trace_log, out)

    state = LayoutWorkflowState(**final) if isinstance(final, dict) else final
    files = dict(state.files)
    files["workflow_trace"] = str(out / "workflow_trace.json")

    assert state.intent is not None and state.layout_dsl is not None
    assert state.generate is not None and state.evidence is not None
    return FromTextResult(
        intent=state.intent,
        spec=state.layout_dsl,
        generate=state.generate,
        evidence=state.evidence,
        optimization=state.optimization,
        output_dir=out,
        files=files,
        circuit_simulations=dict(state.circuit_simulations),
    )
