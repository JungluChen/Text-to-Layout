"""Typed parameters for ground-plane flux-trapping perforation arrays."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class KeepOutRect(BaseModel):
    """Axis-aligned region (µm) that must stay free of holes, e.g. a CPW trace."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @model_validator(mode="after")
    def ordered(self) -> KeepOutRect:
        if self.xmax <= self.xmin or self.ymax <= self.ymin:
            raise ValueError("keep-out rectangle must have positive width and height")
        return self


class PerforationSpec(BaseModel):
    """Square hole array within a ground-plane window.

    Holes are placed on a regular grid with pitch ``pitch_um`` and are only
    emitted when the whole hole lies inside the window and at least
    ``keep_out_margin_um`` away from every keep-out rectangle. Holes are
    emitted on ``hole_layer`` (a *subtractive* layer; the exporter or DRC deck
    decides how it combines with ``metal``). The ground window itself is
    emitted on ``metal`` when ``emit_ground`` is true.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    window_width_um: float = Field(gt=0)
    window_height_um: float = Field(gt=0)
    hole_size_um: float = Field(gt=0, description="Square hole edge length (µm).")
    pitch_um: float = Field(gt=0, description="Center-to-center hole pitch (µm).")
    keep_out_margin_um: float = Field(
        default=10.0, ge=0, description="Clearance between a hole edge and a keep-out edge."
    )
    edge_margin_um: float = Field(
        default=5.0, ge=0, description="Clearance between a hole edge and the window edge."
    )
    keep_outs: tuple[KeepOutRect, ...] = Field(
        default=(), description="Trace/launcher regions in window-local coordinates."
    )
    metal: str = Field(default="M1")
    hole_layer: str = Field(default="M1_HOLE")
    emit_ground: bool = Field(default=True)

    @model_validator(mode="after")
    def holes_fit(self) -> PerforationSpec:
        if self.hole_size_um >= self.pitch_um:
            raise ValueError("pitch_um must exceed hole_size_um so holes never merge")
        if self.hole_size_um + 2 * self.edge_margin_um > min(
            self.window_width_um, self.window_height_um
        ):
            raise ValueError("window is too small for one hole plus edge margins")
        return self
