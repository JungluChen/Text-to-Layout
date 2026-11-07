"""Typed parameters for a smooth Euler (clothoid) CPW bend."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CPWEulerBendSpec(BaseModel):
    """A CPW bend whose curvature ramps linearly (Euler spiral) instead of jumping.

    The centerline starts at ``origin`` heading +y and turns through
    ``angle_deg`` (positive = counter-clockwise / towards -x). ``euler_fraction``
    is the share of the total angle spent in the two clothoid ramps; ``1.0`` is
    a pure Euler bend, smaller values insert a constant-radius arc in the middle
    (the gdsfactory/PHIDL ``p`` convention). ``min_radius_um`` is the radius of
    curvature at the point of maximum curvature.

    Ground planes follow the centerline at a constant lateral clearance of
    ``gap_um``; the inner ground edge must stay strictly inside the osculating
    circle, otherwise the offset self-intersects and the spec is rejected.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    center_width_um: float = Field(gt=0, description="Center conductor width (µm).")
    gap_um: float = Field(gt=0, description="Conductor-to-ground clearance (µm).")
    ground_width_um: float = Field(default=50.0, gt=0, description="Ground strip width (µm).")
    min_radius_um: float = Field(gt=0, description="Minimum centerline radius (µm).")
    angle_deg: float = Field(
        default=90.0, gt=-360.0, lt=360.0, description="Signed total turn angle (deg)."
    )
    euler_fraction: float = Field(
        default=1.0, gt=0.0, le=1.0, description="Share of the turn spent in clothoid ramps."
    )
    points_per_bend: int = Field(
        default=64, ge=8, le=4096, description="Centerline samples (deterministic)."
    )
    metal: str = Field(default="M1", description="Metal layer for signal and grounds.")

    @model_validator(mode="after")
    def clearance_fits_curvature(self) -> CPWEulerBendSpec:
        if self.angle_deg == 0.0:
            raise ValueError("angle_deg must be non-zero; use CPW for straight segments")
        outer_offset = self.center_width_um / 2.0 + self.gap_um + self.ground_width_um
        if outer_offset >= self.min_radius_um:
            raise ValueError(
                "min_radius_um must exceed center_width_um/2 + gap_um + ground_width_um "
                f"({outer_offset} µm) so the inner ground edge does not self-intersect"
            )
        return self
