"""Typed parameters for a square planar spiral inductor."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SpiralInductorSpec(BaseModel):
    """Geometry and cross-section of an open square spiral."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    turns: int = Field(ge=2, le=30)
    outer_dimension_um: float = Field(gt=0)
    trace_width_um: float = Field(gt=0)
    spacing_um: float = Field(gt=0)
    thickness_um: float = Field(default=0.2, gt=0)
    metal: str = Field(default="M1")

    @model_validator(mode="after")
    def winding_fits_outer_dimension(self) -> SpiralInductorSpec:
        required = (
            2.0 * self.turns * self.trace_width_um
            + 2.0 * (self.turns - 1) * self.spacing_um
        )
        if self.outer_dimension_um <= required:
            raise ValueError(
                f"outer_dimension_um must exceed {required:g} um for the requested winding"
            )
        return self
