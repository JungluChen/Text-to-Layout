"""Context object passed to every verification check."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from textlayout.models import Geometry, Technology
from textlayout.schemas.dsl import LayoutSpec


@dataclass(frozen=True, slots=True)
class VerificationContext:
    """Everything a check might need.

    ``component_built`` records whether geometry generation actually succeeded —
    the equivalent of Text-to-CAD's "the STEP artifact was produced" gate.
    """

    spec: LayoutSpec
    params: BaseModel
    geometry: Geometry
    technology: Technology
    component_built: bool = True

    @property
    def param_dict(self) -> dict[str, Any]:
        return self.params.model_dump()

    @property
    def metal_layer(self) -> str:
        """Best-effort resolution of the primary conductor layer."""
        params = self.param_dict
        for key in ("metal", "metal_layer"):
            value = params.get(key)
            if isinstance(value, str):
                return value
        layers = self.geometry.layers()
        return layers[0] if layers else "M1"
