"""Typed parameters for the multi-device research test-chip tile."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TestChipSpec(BaseModel):
    """A research tile combining an IDC, a CPW line, and a spiral inductor,
    plus corner alignment marks and a geometric title label.

    All sub-device parameters share the semantics of their standalone specs
    (``IDCSpec``, ``CPWSpec``, ``SpiralInductorSpec``); the tile only adds
    placement, alignment marks, and the label.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tile_width_um: float = Field(default=2000.0, gt=0)
    tile_height_um: float = Field(default=2000.0, gt=0)
    margin_um: float = Field(default=150.0, gt=0, description="Keep-out from the tile edge (µm).")
    title: str = Field(default="TEXT-TO-LAYOUT", max_length=24)
    title_cell_um: float = Field(default=8.0, gt=0, description="Label font pixel size (µm).")

    alignment_mark_size_um: float = Field(default=80.0, gt=0)
    alignment_mark_width_um: float = Field(default=12.0, gt=0)

    # IDC sub-device.
    idc_finger_pairs: int = Field(default=20, gt=0, le=2000)
    idc_finger_width_um: float = Field(default=4.0, gt=0)
    idc_gap_um: float = Field(default=2.0, gt=0)
    idc_overlap_um: float = Field(default=250.0, gt=0)
    idc_bus_width_um: float = Field(default=25.0, gt=0)

    # CPW sub-device.
    cpw_center_width_um: float = Field(default=10.0, gt=0)
    cpw_gap_um: float = Field(default=6.0, gt=0)
    cpw_ground_width_um: float = Field(default=50.0, gt=0)
    cpw_length_um: float = Field(default=600.0, gt=0)

    # Spiral sub-device.
    spiral_turns: int = Field(default=4, ge=2, le=30)
    spiral_outer_dimension_um: float = Field(default=300.0, gt=0)
    spiral_trace_width_um: float = Field(default=4.0, gt=0)
    spiral_spacing_um: float = Field(default=2.0, gt=0)

    metal_layer: str = Field(default="M1")
    text_layer: str = Field(default="TEXT")

    @model_validator(mode="after")
    def sub_blocks_fit_tile(self) -> TestChipSpec:
        usable_w = self.tile_width_um - 2 * self.margin_um
        usable_h = self.tile_height_um - 2 * self.margin_um
        if usable_w <= 0 or usable_h <= 0:
            raise ValueError("margin_um leaves no usable area inside the tile")
        idc_width = 2 * self.idc_finger_pairs * self.idc_finger_width_um + (
            2 * self.idc_finger_pairs - 1
        ) * self.idc_gap_um
        half_w = usable_w / 2.0
        half_h = usable_h / 2.0
        if idc_width > half_w:
            raise ValueError("IDC is too wide for its tile quadrant")
        if self.cpw_length_um > half_h:
            raise ValueError("CPW line is too long for its tile quadrant")
        if self.spiral_outer_dimension_um > min(half_w, half_h):
            raise ValueError("spiral inductor does not fit its tile quadrant")
        return self
