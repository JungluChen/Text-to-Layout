"""Typed state carried through the LangGraph layout workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from textlayout.evidence import QuantityEvidence
from textlayout.optimization import IDCOptimizationResult
from textlayout.prompt import DesignIntent
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation import SimulationResult
from textlayout.verification.klayout_readback import ReadbackResult
from textlayout.workflows.generate import GenerateResult

#: Retune budget for the solver-in-the-loop capacitance tuning cycle.
MAX_SOLVER_ITERATIONS = 5


class LayoutWorkflowState(BaseModel):
    """Everything a node may read or update. LangGraph merges node returns."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Request (immutable inputs).
    prompt: str
    output_dir: Path
    tolerance_percent: float = 5.0
    execute_solver: bool = True
    solver_executable: str | None = None

    # Pipeline products.
    intent: DesignIntent | None = None
    layout_dsl: LayoutSpec | None = None
    jpa_sizing: dict[str, Any] | None = None
    optimization: IDCOptimizationResult | None = None
    sized_parameters: dict[str, Any] = Field(default_factory=dict)
    circuit_requests: dict[str, tuple[bool, bool]] = Field(default_factory=dict)
    lc_inductance_nh: Any = None
    target_capacitance_pf: float | None = None
    target_inductance_nh: float | None = None

    generate: GenerateResult | None = None
    readback: ReadbackResult | None = None
    geometry_status: str | None = None
    verification_result: dict[str, Any] | None = None

    simulation: SimulationResult | None = None
    evidence: QuantityEvidence | None = None
    simulation_result: dict[str, Any] | None = None
    evidence_status: str | None = None
    circuit_simulations: dict[str, SimulationResult] = Field(default_factory=dict)
    physics_verified: bool = False

    # Solver-in-the-loop bookkeeping.
    iteration: int = 0
    solver_iterations: list[dict[str, Any]] = Field(default_factory=list)

    # Artifact map (kind → path) and diagnostics.
    files: dict[str, str] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)
