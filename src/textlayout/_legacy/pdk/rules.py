"""Fabrication design-rule models for superconducting layouts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FabricationRuleSet:
    minimum_jj_size_um: float
    maximum_jj_size_um: float
    minimum_jj_area_um2: float
    maximum_jj_area_um2: float
    minimum_cpw_gap_um: float
    minimum_metal_width_um: float
    minimum_spacing_um: float
    minimum_via_size_um: float
    via_enclosure_um: float
    alignment_tolerance_um: float
    lithography_resolution_um: float

    def validate_junction(self, width_um: float, height_um: float) -> list[str]:
        area = width_um * height_um
        errors: list[str] = []
        if width_um < self.minimum_jj_size_um or height_um < self.minimum_jj_size_um:
            errors.append("junction dimensions are below minimum JJ size")
        if width_um > self.maximum_jj_size_um or height_um > self.maximum_jj_size_um:
            errors.append("junction dimensions exceed maximum JJ size")
        if area < self.minimum_jj_area_um2:
            errors.append("junction area is below minimum process area")
        if area > self.maximum_jj_area_um2:
            errors.append("junction area exceeds maximum process area")
        return errors

    def validate_cpw(self, center_width_um: float, gap_um: float) -> list[str]:
        errors: list[str] = []
        if center_width_um < self.minimum_metal_width_um:
            errors.append("CPW center trace is below minimum metal width")
        if gap_um < self.minimum_cpw_gap_um:
            errors.append("CPW gap is below minimum process gap")
        return errors

    def to_dict(self) -> dict[str, float]:
        return self.__dict__.copy()


DEFAULT_FABRICATION_RULES = FabricationRuleSet(
    minimum_jj_size_um=0.10,
    maximum_jj_size_um=10.0,
    minimum_jj_area_um2=0.01,
    maximum_jj_area_um2=10.0,
    minimum_cpw_gap_um=1.0,
    minimum_metal_width_um=0.20,
    minimum_spacing_um=0.20,
    minimum_via_size_um=0.30,
    via_enclosure_um=0.20,
    alignment_tolerance_um=0.050,
    lithography_resolution_um=0.050,
)
