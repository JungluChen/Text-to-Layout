"""Typed parameter schema for the Interdigital Capacitor (IDC) generator.

Field constraints encode the firewall: an LLM cannot produce a zero-width finger
or a negative gap — pydantic rejects it before any geometry is built.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class IDCSpec(BaseModel):
    """Parameters for an interdigital (interdigitated) capacitor.

    Geometry: two combs (bottom + top buses) whose fingers interleave. Adjacent
    opposing fingers run parallel over ``overlap_um`` separated laterally by
    ``gap_um``; this overlap region is what sets the capacitance.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    finger_pairs: int = Field(gt=0, le=2000, description="Number of finger pairs (combs of N each).")
    finger_width_um: float = Field(gt=0, description="Width of each finger (µm).")
    gap_um: float = Field(gt=0, description="Lateral gap between adjacent fingers (µm).")
    overlap_um: float = Field(gt=0, description="Parallel overlap length of opposing fingers (µm).")
    bus_width_um: float = Field(gt=0, description="Width of the top/bottom bus bars (µm).")
    metal_layer: str = Field(default="M1", description="Metal layer name for all conductors.")
