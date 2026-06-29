"""Typed parameter schema for the Coplanar Waveguide (CPW) generator.

This schema is owned by the CPW generator. Field-level constraints (``gt=0``)
mean an LLM cannot smuggle a non-physical value past the firewall: invalid
parameters are rejected by pydantic *before* any geometry is built.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CPWSpec(BaseModel):
    """Parameters for a straight coplanar-waveguide segment.

    Geometry: a center signal conductor of width ``center_width_um`` flanked by a
    gap of ``gap_um`` on each side, then a ground plane of width
    ``ground_width_um`` on each side. The segment runs along +y for ``length_um``.
    Signal and grounds are coplanar (same ``metal`` layer).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    center_width_um: float = Field(gt=0, description="Center conductor width (µm).")
    gap_um: float = Field(gt=0, description="Gap between center conductor and ground (µm).")
    length_um: float = Field(gt=0, description="Length of the segment along +y (µm).")
    ground_width_um: float = Field(
        default=50.0, gt=0, description="Width of each ground plane (µm)."
    )
    metal: str = Field(default="M1", description="Metal layer name for all conductors.")
