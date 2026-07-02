"""Typed parameters for a capacitively coupled quarter-wave CPW resonator."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class QuarterWaveResonatorSpec(BaseModel):
    """Straight quarter-wave CPW hanger with an explicit open and short."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    center_width_um: float = Field(gt=0)
    gap_um: float = Field(gt=0)
    length_um: float = Field(gt=0)
    ground_width_um: float = Field(default=50.0, gt=0)
    coupling_gap_um: float = Field(gt=0)
    feedline_length_um: float = Field(default=500.0, gt=0)
    short_width_um: float = Field(default=10.0, gt=0)
    metal: str = Field(default="M1")
