"""Pydantic v2 request/response models for the plugin API.

These are the contract an AI tool-caller (ChatGPT custom GPT action, Claude, …)
reads from the auto-generated OpenAPI schema. Request bodies for generate /
verify / preview / report are the Layout DSL itself (:class:`LayoutSpec`), so an
example DSL file can be POSTed verbatim.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from textlayout.schemas.dsl import LayoutSpec

# Request bodies reuse the DSL directly.
LayoutRequest = LayoutSpec


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    components: list[str] = Field(description="Registered generator component names.")
    technologies: list[str] = Field(description="Available technologies/PDKs.")
    formats: list[str] = Field(description="Available export formats.")


class CheckModel(BaseModel):
    """One verification check; dynamic value_*/limit_* keys allowed."""

    model_config = {"extra": "allow"}

    name: str
    status: str


class VerificationModel(BaseModel):
    status: str = Field(description="'pass' or 'fail'.")
    component: str
    checks: list[dict[str, Any]]
    warnings: list[str]
    errors: list[str]


class GenerateResponse(BaseModel):
    status: str = Field(description="'pass' or 'fail' (mirrors verification).")
    component: str
    summary: dict[str, Any]
    verification: VerificationModel
    artifacts: dict[str, str] = Field(
        default_factory=dict, description="Inline text artifacts (json, svg)."
    )
    files: dict[str, str] = Field(
        default_factory=dict, description="Paths to written files keyed by format."
    )
    evidence: dict[str, Any] = Field(
        default_factory=dict, description="Research, equations, assumptions, and references."
    )


class VerifyResponse(VerificationModel):
    """Verification report (same shape as the embedded verification block)."""


class PreviewResponse(BaseModel):
    format: str = "svg"
    component: str
    svg: str


class ExportResponse(BaseModel):
    component: str
    format: str
    file: str = Field(description="Absolute path to the written artifact.")
    bytes: int
    verification_status: str


class SimulationStep(BaseModel):
    stage: str
    description: str


class ReportResponse(BaseModel):
    component: str
    summary: dict[str, Any]
    verification: VerificationModel
    evidence: dict[str, Any]
    files: dict[str, str]
    simulation_next_steps: list[SimulationStep]


class ResearchResponse(BaseModel):
    status: str = "ready"
    component: str
    evidence: dict[str, Any]


class BenchmarkResponse(GenerateResponse):
    report_markdown: str
    simulation: dict[str, Any]


class SimulationResponse(BaseModel):
    component: str
    verification: VerificationModel
    simulation: dict[str, Any]


class FromTextRequest(BaseModel):
    """Natural-language layout request (deterministic parser; no LLM needed)."""

    prompt: str = Field(
        description="e.g. 'Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap'."
    )
    output_dir: str | None = Field(
        default=None,
        description="Optional output directory; defaults to a workspace subfolder.",
    )
    tolerance_percent: float = Field(default=5.0, gt=0)
    execute_solver: bool = Field(
        default=True,
        description="Attempt to run FasterCap/FastCap if installed; skipped honestly if absent.",
    )


class FromTextResponse(BaseModel):
    status: str = Field(description="'ok' or 'verification_failed'.")
    component: str
    target: dict[str, float]
    intent: dict[str, Any] = Field(description="Parsed design intent (intent.json).")
    simulation_status: str = Field(
        description="Evidence status: ANALYTICAL_ONLY | SIMULATION_INPUT_PREPARED | "
        "SIMULATION_EXECUTED | PHYSICS_VERIFIED | FAILED | SKIPPED_SOLVER_ABSENT."
    )
    simulation_summary: str
    evidence: dict[str, Any] = Field(description="Typed QuantityEvidence record.")
    optimization: dict[str, Any] | None = Field(
        default=None, description="Closed-loop tuning record, when a target was optimised."
    )
    verification: VerificationModel
    artifacts: dict[str, str] = Field(description="Artifact file names keyed by kind.")
    files: dict[str, str] = Field(description="Absolute paths keyed by kind.")
    output_dir: str


class ErrorResponse(BaseModel):
    error: str = Field(description="Error type, e.g. 'InvalidParametersError'.")
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)
