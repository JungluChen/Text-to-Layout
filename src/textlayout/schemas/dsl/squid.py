"""Typed parameters for a generic two-junction SQUID test structure."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SQUIDSpec(BaseModel):
    """Symmetric loop with two process-placeholder junction polygons."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    loop_inner_width_um: float = Field(gt=0)
    loop_inner_height_um: float = Field(gt=0)
    trace_width_um: float = Field(gt=0)
    junction_gap_um: float = Field(gt=0)
    junction_width_um: float = Field(gt=0)
    pad_width_um: float = Field(default=40.0, gt=0)
    pad_height_um: float = Field(default=30.0, gt=0)
    metal: str = Field(default="M1")
    junction_layer: str = Field(default="JJ")

    @model_validator(mode="after")
    def junctions_fit_loop_arms(self) -> SQUIDSpec:
        if self.junction_width_um > self.trace_width_um:
            raise ValueError("junction_width_um cannot exceed trace_width_um")
        if self.junction_gap_um >= self.loop_inner_height_um:
            raise ValueError("junction_gap_um must be smaller than loop_inner_height_um")
        return self
