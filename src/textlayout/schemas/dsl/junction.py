"""Typed parameters for multi-layer Josephson-junction pad structures."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class JosephsonJunctionSpec(BaseModel):
    """Dolan-bridge or Manhattan-cross double-angle-evaporation junction.

    Layers are intentionally separate because fabrication treats them so:

    ``metal``
        Base (pre-existing) metallisation carrying the two contact pads.
    ``base_layer`` / ``counter_layer``
        First and second shadow-evaporated electrodes. Their overlap is the
        junction area.
    ``undercut_layer``
        Resist undercut / bridge region exposed around the junction (Dolan only
        by default; Manhattan sets a square around the crossing).
    ``bandage_layer``
        Ion-milled bandage patches that galvanically connect each electrode to
        its ``metal`` pad.

    For ``style="dolan"`` the junction area is ``junction_width_um *
    overlap_um``; for ``style="manhattan"`` it is ``junction_width_um *
    finger_width_um``. If ``critical_current_density_ua_per_um2`` is given the
    spec also reports the Ambegaokar-Baratoff-independent *geometric*
    estimates ``I_c``, ``L_J`` and ``E_J/h``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    style: Literal["dolan", "manhattan"] = Field(default="dolan")
    junction_width_um: float = Field(gt=0, description="Width of the first electrode finger.")
    finger_width_um: float = Field(
        default=0.2, gt=0, description="Second electrode finger width (Manhattan) (µm)."
    )
    overlap_um: float = Field(default=0.2, gt=0, description="Electrode overlap (Dolan) (µm).")
    bridge_um: float = Field(default=0.3, gt=0, description="Dolan resist bridge length (µm).")
    lead_width_um: float = Field(default=1.0, gt=0)
    lead_length_um: float = Field(default=10.0, gt=0)
    pad_width_um: float = Field(default=20.0, gt=0)
    pad_height_um: float = Field(default=20.0, gt=0)
    bandage_size_um: float = Field(default=4.0, gt=0)
    undercut_um: float = Field(default=0.5, ge=0)
    metal: str = Field(default="M1")
    base_layer: str = Field(default="JJ1")
    counter_layer: str = Field(default="JJ2")
    undercut_layer: str = Field(default="JJ_UNDERCUT")
    bandage_layer: str = Field(default="BANDAGE")
    critical_current_density_ua_per_um2: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def geometry_is_consistent(self) -> JosephsonJunctionSpec:
        if self.junction_width_um > self.lead_width_um:
            raise ValueError("junction_width_um cannot exceed lead_width_um")
        if self.style == "manhattan" and self.finger_width_um > self.lead_width_um:
            raise ValueError("finger_width_um cannot exceed lead_width_um")
        if self.bandage_size_um > min(self.pad_width_um, self.pad_height_um):
            raise ValueError("bandage_size_um must fit inside the pad")
        return self

    @property
    def junction_area_um2(self) -> float:
        if self.style == "dolan":
            return self.junction_width_um * self.overlap_um
        return self.junction_width_um * self.finger_width_um
