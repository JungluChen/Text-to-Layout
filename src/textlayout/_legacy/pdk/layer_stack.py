"""LayerMap/LayerStack style PDK objects inspired by gdsfactory."""

from __future__ import annotations

from dataclasses import dataclass

from textlayout._legacy.process import (
    CHIP_BOUNDARY,
    JJ,
    KEEPOUT,
    M1,
    M2,
    M3,
    MARKER,
    PORT,
    UNDERCUT,
    VIA12,
    VIA23,
    Layer,
)


@dataclass(frozen=True)
class LayerMap:
    substrate: Layer = CHIP_BOUNDARY
    ground_plane: Layer = M1
    cpw_center_trace: Layer = M2
    cpw_gap: Layer = KEEPOUT
    bottom_metal: Layer = M1
    tunnel_barrier: Layer = JJ
    top_metal: Layer = M2
    global_routing: Layer = M3
    via12: Layer = VIA12
    via23: Layer = VIA23
    resist_opening: Layer = UNDERCUT
    keepout: Layer = KEEPOUT
    port: Layer = PORT
    label_marker: Layer = MARKER

    def to_dict(self) -> dict[str, list[int]]:
        return {name: [int(layer[0]), int(layer[1])] for name, layer in self.__dict__.items()}


@dataclass(frozen=True)
class LayerLevel:
    name: str
    layer: Layer
    material: str
    thickness_nm: float
    zmin_nm: float
    role: str


@dataclass(frozen=True)
class QuantumLayerStack:
    layers: tuple[LayerLevel, ...]

    def by_name(self, name: str) -> LayerLevel:
        for level in self.layers:
            if level.name == name:
                return level
        raise KeyError(name)

    def to_dict(self) -> dict[str, dict[str, float | str | list[int]]]:
        return {
            level.name: {
                "layer": [int(level.layer[0]), int(level.layer[1])],
                "material": level.material,
                "thickness_nm": level.thickness_nm,
                "zmin_nm": level.zmin_nm,
                "role": level.role,
            }
            for level in self.layers
        }


DEFAULT_LAYER_MAP = LayerMap()

DEFAULT_LAYER_STACK = QuantumLayerStack(
    layers=(
        LayerLevel("substrate", CHIP_BOUNDARY, "Si", 254_000.0, -254_000.0, "chip boundary"),
        LayerLevel("M1", M1, "Nb", 180.0, 0.0, "ground and bottom electrode"),
        LayerLevel("JJ", JJ, "AlOx", 2.0, 180.0, "tunnel barrier"),
        LayerLevel("M2", M2, "Nb", 200.0, 182.0, "top electrode and CPW signal"),
        LayerLevel("M3", M3, "Nb", 350.0, 382.0, "global microwave routing"),
        LayerLevel("VIA12", VIA12, "Nb", 200.0, 180.0, "M1/M2 via"),
        LayerLevel("VIA23", VIA23, "Nb", 250.0, 382.0, "M2/M3 via"),
        LayerLevel("UNDERCUT", UNDERCUT, "air", 0.0, 0.0, "junction resist opening"),
        LayerLevel("KEEPOUT", KEEPOUT, "air", 0.0, 0.0, "exclusion annotation"),
        LayerLevel("PORT", PORT, "marker", 0.0, 0.0, "solver port marker"),
    )
)
