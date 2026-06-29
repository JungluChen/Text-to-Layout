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
"""

from __future__ import annotations

import os
import uuid

from fastapi import FastAPI, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

import textlayout
from textlayout import build_default_workflow
from textlayout.backend.api_models import (
    ErrorResponse,
    ExportResponse,
    GenerateResponse,
    HealthResponse,
    PreviewResponse,
    ReportResponse,
    SimulationStep,
    VerifyResponse,
)
from textlayout.backend.settings import Settings
from textlayout.errors import (
    ExportError,
    InvalidParametersError,
    TextLayoutError,
    UnknownComponentError,
    UnknownExporterError,
    UnknownTechnologyError,
)
from textlayout.schemas.dsl import LayoutSpec
from textlayout.workflows import GenerateResult, GenerateWorkflow

_STATUS_CODES: dict[type[TextLayoutError], int] = {
    InvalidParametersError: 400,
    UnknownComponentError: 400,
    UnknownTechnologyError: 400,
    UnknownExporterError: 400,
    ExportError: 500,
}

SIMULATION_NEXT_STEPS = [
    SimulationStep(stage="import", description="Import generated GDS into HFSS / Q3D / ADS."),
    SimulationStep(stage="setup", description="Assign metal/substrate materials, ports, boundaries."),
    SimulationStep(stage="extract", description="EM-extract C, L, Q, S-parameters, resonance."),
    SimulationStep(stage="compare", description="Compare extracted values against the design target."),
    SimulationStep(stage="optimize", description="Feed deltas back into a DSL parameter-tuning loop."),
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
        )

    @app.post("/layout/verify", response_model=VerifyResponse, tags=["layout"])
    async def verify(spec: LayoutSpec) -> VerifyResponse:
        report = await run_in_threadpool(workflow.verify_only, spec)
        return VerifyResponse(**report.to_dict())

    @app.post("/layout/preview", response_model=PreviewResponse, tags=["layout"])
    async def preview(spec: LayoutSpec) -> PreviewResponse:
        result = await run_in_threadpool(_run, workflow, spec, settings, ["svg"], False)
        return PreviewResponse(component=spec.component, svg=result.artifacts["svg"])

    @app.post("/layout/export", response_model=ExportResponse, tags=["layout"])
    async def export(spec: LayoutSpec, format: str = Query(default="gds")) -> ExportResponse:
        result = await run_in_threadpool(_run, workflow, spec, settings, [format])
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
            files=dict(result.files),
            simulation_next_steps=SIMULATION_NEXT_STEPS,
        )

    return app


def _run(
    workflow: GenerateWorkflow,
    spec: LayoutSpec,
    settings: Settings,
    formats: list[str] | None,
    write: bool = True,
) -> GenerateResult:
    output_dir = settings.workspace / uuid.uuid4().hex if write else None
    return workflow.run(spec, formats=formats, output_dir=output_dir)
