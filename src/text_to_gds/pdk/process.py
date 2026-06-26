"""Named superconducting process presets."""

from __future__ import annotations

from dataclasses import dataclass

from text_to_gds.pdk.layer_stack import DEFAULT_LAYER_MAP, DEFAULT_LAYER_STACK, LayerMap, QuantumLayerStack
from text_to_gds.pdk.materials import DEFAULT_MATERIAL_CATALOG, MaterialCatalog
from text_to_gds.pdk.rules import DEFAULT_FABRICATION_RULES, FabricationRuleSet


@dataclass(frozen=True)
class ManhattanProcess:
    bottom_layer: str = "M1"
    top_layer: str = "M2"
    jj_min_area: float = 0.01
    jj_max_area: float = 10.0
    alignment_error: float = 50e-3
    layer_map: LayerMap = DEFAULT_LAYER_MAP
    layer_stack: QuantumLayerStack = DEFAULT_LAYER_STACK
    materials: MaterialCatalog = DEFAULT_MATERIAL_CATALOG
    rules: FabricationRuleSet = DEFAULT_FABRICATION_RULES

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.jj_min_area <= 0.0:
            errors.append("jj_min_area must be positive")
        if self.jj_max_area <= self.jj_min_area:
            errors.append("jj_max_area must exceed jj_min_area")
        if self.alignment_error < 0.0:
            errors.append("alignment_error must be non-negative")
        return errors

    def to_dict(self) -> dict[str, object]:
        return {
            "bottom_layer": self.bottom_layer,
            "top_layer": self.top_layer,
            "jj_min_area": self.jj_min_area,
            "jj_max_area": self.jj_max_area,
            "alignment_error": self.alignment_error,
            "layer_map": self.layer_map.to_dict(),
            "layer_stack": self.layer_stack.to_dict(),
            "materials": self.materials.to_dict(),
            "rules": self.rules.to_dict(),
        }


DEFAULT_MANHATTAN_PROCESS = ManhattanProcess()
