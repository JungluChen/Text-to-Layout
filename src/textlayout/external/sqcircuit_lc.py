"""Typed preparation boundary for the audited SQcircuit LC model.

Preparation imports no optional numerical package and never executes a solver.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from textlayout.evidence.contract import EvidenceStatus


class SQcircuitLCRequest(BaseModel):
    """Explicit SI elements; branch capacitance is additional parallel capacitance."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False, frozen=True)
    capacitance_f: float = Field(ge=8e-14, le=1e-13)
    inductance_h: float = Field(ge=6e-8, le=1e-7)
    branch_capacitance_f: float = Field(ge=1e-20, le=1e-15)


class SQcircuitLCPlan(BaseModel):
    """Fixed bounded diagnostic, not proof of installed or executed software."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_name: Literal["textlayout.sqcircuit-lc-plan.v1"] = "textlayout.sqcircuit-lc-plan.v1"
    request: SQcircuitLCRequest
    method: Literal["SQcircuit Hamiltonian + numpy.linalg.eigh"] = (
        "SQcircuit Hamiltonian + numpy.linalg.eigh"
    )
    sqcircuit_version: Literal["1.0.0"] = "1.0.0"
    source_revision: Literal["7cdc826a63224a8fb860362224a4a530e80aa1d7"] = (
        "7cdc826a63224a8fb860362224a4a530e80aa1d7"
    )
    truncations: tuple[Literal[10], Literal[20], Literal[30]] = (10, 20, 30)
    levels: Literal[6] = 6
    reference_limit_hz: float = Field(default=1.0, ge=1.0, le=1.0)
    scaled_residual_limit: float = Field(default=1e-12, ge=1e-12, le=1e-12)
    hermiticity_limit: float = Field(default=1e-14, ge=1e-14, le=1e-14)


class PreparedSQcircuitLC(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal[EvidenceStatus.SIMULATION_INPUT_PREPARED] = (
        EvidenceStatus.SIMULATION_INPUT_PREPARED
    )
    input_path: str
    input_sha256: str


def prepare_sqcircuit_lc(request: SQcircuitLCRequest, *, output_dir: Path) -> PreparedSQcircuitLC:
    """Write a fixed plan into a fresh directory; no import, probe or execution.

    Raises FileExistsError for an existing output directory, preserving prior
    evidence. No numerical quantities or solver availability claims are returned.
    """
    request = SQcircuitLCRequest.model_validate(request.model_dump())
    plan = SQcircuitLCPlan(request=request)
    payload = (plan.model_dump_json(indent=2) + "\n").encode("utf-8")
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    input_path = output_dir / "request.json"
    input_path.write_bytes(payload)
    return PreparedSQcircuitLC(
        input_path=str(input_path), input_sha256=hashlib.sha256(payload).hexdigest()
    )
