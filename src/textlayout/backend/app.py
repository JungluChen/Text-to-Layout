"""FastAPI application factory for the Text-to-Layout plugin server.

`create_app()` is a factory (no import-time global app) that wires a
:class:`GenerateWorkflow` via dependency injection and exposes the plugin
endpoints. The same workflow core also backs the CLI and the MCP server, so all
three entry points share one verified pipeline.

Endpoints
---------
- ``GET  /health``          — liveness + capability discovery
- ``POST /layout/generate`` — DSL → geometry → verify → artifacts
- ``POST /layout/verify``   — DSL → geometry → verification report
- ``POST /layout/preview``  — DSL → SVG preview
- ``POST /layout/export``   — DSL → single artifact written to disk (``?format=gds``)
- ``POST /layout/report``   — DSL → full report incl. simulation next steps
- ``POST /layout/simulate`` — verified DSL → prepared or executed solver evidence
- ``POST /layout/benchmark``— verified DSL → reproducible benchmark artifacts
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

import textlayout
from textlayout import build_default_workflow
from textlayout.backend.api_models import (
    ErrorResponse,
    BenchmarkResponse,
    ExportResponse,
    FromTextRequest,
    FromTextResponse,
    GenerateResponse,
    HealthResponse,
    PreviewResponse,
    ResearchResponse,
    ReportResponse,
    SimulationResponse,
    SimulationStep,
    VerifyResponse,
)
from textlayout.backend.settings import Settings
from textlayout.errors import (
    ExportError,
    InvalidParametersError,
    MissingResearchError,
    PromptParseError,
    TextLayoutError,
    UnknownComponentError,
    UnknownExporterError,
    UnknownTechnologyError,
    VerificationFailedError,
)
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation import simulate_layout
from textlayout.workflows import FromTextWorkflow, GenerateResult, GenerateWorkflow

_STATUS_CODES: dict[type[TextLayoutError], int] = {
    PromptParseError: 400,
    InvalidParametersError: 400,
    UnknownComponentError: 400,
    UnknownTechnologyError: 400,
    UnknownExporterError: 400,
    ExportError: 500,
    MissingResearchError: 400,
    VerificationFailedError: 422,
}

SIMULATION_NEXT_STEPS = [
    SimulationStep(
        stage="prepare",
        description="Prepare open-source FasterCap/FastCap or openEMS inputs from verified geometry.",
    ),
    SimulationStep(
        stage="setup", description="Assign metal/substrate materials, ports, boundaries."
    ),
    SimulationStep(stage="extract", description="EM-extract C, L, Q, S-parameters, resonance."),
    SimulationStep(
        stage="compare", description="Compare extracted values against the design target."
    ),
    SimulationStep(
        stage="optimize", description="Feed deltas back into a DSL parameter-tuning loop."
    ),
    SimulationStep(stage="report", description="Emit a signed-off report with provenance."),
]

DESCRIPTION = (
    "Natural-language IC layout: a structured Layout DSL is turned into "
    "deterministic gdsfactory geometry, verified against design rules, and "
    "exported to GDS / SVG / JSON. The AI never writes GDS directly."
)


def create_app(
    *,
    workflow: GenerateWorkflow | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    workflow = workflow or build_default_workflow()

    app = FastAPI(
        title=settings.title,
        version=textlayout.__version__,
        description=DESCRIPTION,
    )

    @app.exception_handler(TextLayoutError)
    async def _handle_textlayout_error(request: Request, exc: TextLayoutError) -> JSONResponse:
        status = _STATUS_CODES.get(type(exc), 400)
        detail: dict[str, object] = {}
        for attr in ("component", "technology", "format", "available", "detail"):
            if hasattr(exc, attr):
                detail[attr] = getattr(exc, attr)
        body = ErrorResponse(error=type(exc).__name__, message=str(exc), detail=detail)
        return JSONResponse(status_code=status, content=body.model_dump())

    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    async def health() -> HealthResponse:
        return HealthResponse(
            version=textlayout.__version__,
            components=workflow.component_names,
            technologies=workflow.technology_names,
            formats=workflow.export_formats,
        )

    @app.post("/layout/from-text", response_model=FromTextResponse, tags=["layout"])
    async def from_text(request: FromTextRequest) -> FromTextResponse:
        from_text_workflow = FromTextWorkflow(workflow)
        output_dir = (
            Path(request.output_dir)
            if request.output_dir
            else settings.workspace / "from_text" / uuid.uuid4().hex
        )
        result = await run_in_threadpool(
            from_text_workflow.run,
            request.prompt,
            output_dir,
            tolerance_percent=request.tolerance_percent,
            execute_solver=request.execute_solver,
        )
        return FromTextResponse(
            status="ok" if result.ok else "verification_failed",
            component=result.spec.component,
            target=dict(result.spec.target),
            intent=result.intent.model_dump(mode="json"),
            simulation_status=result.evidence.status.value,
            simulation_summary=result.evidence.summary_line(),
            evidence=result.evidence.model_dump(mode="json"),
            optimization=(
                result.optimization.model_dump(mode="json")
                if result.optimization is not None
                else None
            ),
            verification=VerifyResponse(**result.generate.report.to_dict()),
            artifacts={name: Path(p).name for name, p in result.files.items()},
            files=dict(result.files),
            output_dir=str(result.output_dir),
        )

    @app.post("/layout/generate", response_model=GenerateResponse, tags=["layout"])
    async def generate(spec: LayoutSpec) -> GenerateResponse:
        result = await run_in_threadpool(_run, workflow, spec, settings, None)
        return GenerateResponse(
            status=result.report.status,
            component=spec.component,
            summary=result.summary,
            verification=result.report.to_dict(),
            artifacts=dict(result.artifacts),
            files=dict(result.files),
            evidence=result.research.to_dict(),
        )

    @app.post("/layout/research", response_model=ResearchResponse, tags=["evidence"])
    async def layout_research(spec: LayoutSpec) -> ResearchResponse:
        evidence = await run_in_threadpool(workflow.research_only, spec)
        return ResearchResponse(component=spec.component, evidence=evidence.to_dict())

    @app.post("/layout/verify", response_model=VerifyResponse, tags=["layout"])
    async def verify(spec: LayoutSpec) -> VerifyResponse:
        report = await run_in_threadpool(workflow.verify_only, spec)
        return VerifyResponse(**report.to_dict())

    @app.post("/layout/preview", response_model=PreviewResponse, tags=["layout"])
    async def preview(spec: LayoutSpec) -> PreviewResponse:
        result = await run_in_threadpool(_run, workflow, spec, settings, ["svg"], False)
        _require_verified(result)
        return PreviewResponse(component=spec.component, svg=result.artifacts["svg"])

    @app.post("/layout/export", response_model=ExportResponse, tags=["layout"])
    async def export(spec: LayoutSpec, format: str = Query(default="gds")) -> ExportResponse:
        result = await run_in_threadpool(_run, workflow, spec, settings, [format])
        _require_verified(result)
        path = result.files[format]
        return ExportResponse(
            component=spec.component,
            format=format,
            file=path,
            bytes=os.path.getsize(path),
            verification_status=result.report.status,
        )

    @app.post("/layout/report", response_model=ReportResponse, tags=["layout"])
    async def report(spec: LayoutSpec) -> ReportResponse:
        result = await run_in_threadpool(_run, workflow, spec, settings, None)
        return ReportResponse(
            component=spec.component,
            summary=result.summary,
            verification=result.report.to_dict(),
            evidence=result.research.to_dict(),
            files=dict(result.files),
            simulation_next_steps=SIMULATION_NEXT_STEPS,
        )

    @app.post("/layout/simulate", response_model=SimulationResponse, tags=["simulation"])
    async def simulate(
        spec: LayoutSpec,
        solver: str = Query(default="auto"),
        execute: bool = Query(default=False),
        executable: str | None = Query(default=None),
    ) -> SimulationResponse:
        result = await run_in_threadpool(workflow.run, spec, ())
        _require_verified(result)
        output_dir = settings.workspace / "simulations" / uuid.uuid4().hex
        simulation = await run_in_threadpool(
            simulate_layout,
            spec,
            result.geometry,
            workflow.technology(spec.technology),
            output_dir,
            solver=solver,
            execute=execute,
            executable=executable,
        )
        return SimulationResponse(
            component=spec.component,
            verification=result.report.to_dict(),
            simulation=simulation.to_dict(),
        )

    @app.post("/layout/benchmark", response_model=BenchmarkResponse, tags=["layout"])
    async def benchmark(spec: LayoutSpec) -> BenchmarkResponse:
        result = await run_in_threadpool(
            _run, workflow, spec, settings, None, True, "output", "benchmarks"
        )
        simulation_dir = (
            Path(next(iter(result.files.values()))).parent / "simulation"
            if result.files
            else settings.workspace / "benchmarks" / uuid.uuid4().hex / "simulation"
        )
        simulation = await run_in_threadpool(
            simulate_layout,
            spec,
            result.geometry,
            workflow.technology(spec.technology),
            simulation_dir,
        )
        if "simulation_plan" in result.files:
            Path(result.files["simulation_plan"]).write_text(
                simulation.to_markdown(), encoding="utf-8"
            )
        if "report" in result.files:
            report_path = Path(result.files["report"])
            report_text = report_path.read_text(encoding="utf-8")
            report_path.write_text(
                report_text.replace(
                    "No EM solver was executed by this workflow. The analytical estimate is a design starting point only.",
                    (
                        f"Simulation readiness is Level {simulation.readiness_level} "
                        f"({simulation.readiness_label}). No EM solver was executed; "
                        "the analytical estimate remains a design starting point only."
                    ),
                ),
                encoding="utf-8",
            )
        return BenchmarkResponse(
            status=result.report.status,
            component=spec.component,
            summary=result.summary,
            verification=result.report.to_dict(),
            artifacts=dict(result.artifacts),
            files=dict(result.files),
            evidence=result.research.to_dict(),
            simulation=simulation.to_dict(),
            report_markdown=(
                Path(result.files["report"]).read_text(encoding="utf-8")
                if "report" in result.files
                else ""
            ),
        )

    return app


def _run(
    workflow: GenerateWorkflow,
    spec: LayoutSpec,
    settings: Settings,
    formats: list[str] | None,
    write: bool = True,
    stem: str | None = None,
    namespace: str | None = None,
) -> GenerateResult:
    output_dir = (
        settings.workspace / (namespace or "requests") / uuid.uuid4().hex if write else None
    )
    return workflow.run(spec, formats=formats, output_dir=output_dir, stem=stem)


def _require_verified(result: GenerateResult) -> None:
    if not result.report.passed:
        raise VerificationFailedError(result.spec.component, result.report.to_dict())
