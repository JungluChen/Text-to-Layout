"""SQuADDS MCP integration boundary.

SQuADDS may provide validated-design search results and priors. Those priors
must be regenerated through Text-to-Layout and pass normal geometry/solver gates
before any PHYSICS_VERIFIED claim is made.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SquaddsPrior:
    design_id: str
    hamiltonian_parameters: dict[str, float]
    geometry_priors: dict[str, float]
    dataset_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "textlayout.squadds-prior.v1",
            "source": "SQuADDS",
            "evidence_status": "PRIOR_ONLY",
            "physics_verified": False,
            "design_id": self.design_id,
            "hamiltonian_parameters": dict(self.hamiltonian_parameters),
            "geometry_priors": dict(self.geometry_priors),
            "dataset_metadata": dict(self.dataset_metadata),
        }
