"""Typed parameters for the IDC + CPW measurement test structure."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TestStructureSpec(BaseModel):
    """An IDC device under test fed by two vertical CPW launch sections.

    Layout (bottom to top): GSG launch pad → CPW feed trace → IDC bottom bus →
    IDC fingers → IDC top bus → CPW feed trace → GSG launch pad, flanked by two
    continuous ground planes at ``ground_clearance_um``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Device under test (IDC) — same semantics as IDCSpec.
    finger_pairs: int = Field(default=20, gt=0, le=2000)
    finger_width_um: float = Field(default=4.0, gt=0)
    gap_um: float = Field(default=2.0, gt=0)
    overlap_um: float = Field(default=250.0, gt=0)
    bus_width_um: float = Field(default=25.0, gt=0)

    # CPW feed sections.
    feed_width_um: float = Field(default=10.0, gt=0, description="CPW signal trace width (µm).")
    feed_gap_um: float = Field(default=6.0, gt=0, description="CPW signal-to-ground gap (µm).")
    feed_length_um: float = Field(default=300.0, gt=0, description="Feed trace length (µm).")

    # GSG-style launch regions.
    launch_width_um: float = Field(default=100.0, gt=0, description="Probe pad width (µm).")
    launch_length_um: float = Field(default=120.0, gt=0, description="Probe pad length (µm).")

    # Ground planes.
    ground_clearance_um: float = Field(
        default=30.0, gt=0, description="Clearance from any signal metal to the ground planes (µm)."
    )
    ground_width_um: float = Field(default=150.0, gt=0, description="Ground plane width (µm).")

    metal_layer: str = Field(default="M1")
