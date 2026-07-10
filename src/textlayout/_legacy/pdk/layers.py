"""Named physical layers used by quantum layouts."""

from __future__ import annotations

from dataclasses import dataclass

from textlayout._legacy.process import JJ, KEEPOUT, M1, M2, M3, MARKER, PORT, UNDERCUT, VIA12, VIA23


@dataclass(frozen=True)
class PhysicalLayer:
    name: str
    layer: tuple[int, int]
    role: str
    conductive: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "layer": [self.layer[0], self.layer[1]],
            "role": self.role,
            "conductive": self.conductive,
        }


PHYSICAL_LAYERS: dict[str, PhysicalLayer] = {
    "M1": PhysicalLayer("M1", M1, "ground/bottom_electrode", True),
    "M2": PhysicalLayer("M2", M2, "cpw/top_electrode", True),
    "M3": PhysicalLayer("M3", M3, "global_routing", True),
    "JJ": PhysicalLayer("JJ", JJ, "tunnel_barrier", False),
    "VIA12": PhysicalLayer("VIA12", VIA12, "via", True),
    "VIA23": PhysicalLayer("VIA23", VIA23, "via", True),
    "UNDERCUT": PhysicalLayer("UNDERCUT", UNDERCUT, "shadow_evaporation_undercut", False),
    "PORT": PhysicalLayer("PORT", PORT, "port_marker", False),
    "MARKER": PhysicalLayer("MARKER", MARKER, "annotation", False),
    "KEEPOUT": PhysicalLayer("KEEPOUT", KEEPOUT, "keepout", False),
}

CONDUCTIVE_LAYER_NAMES = tuple(name for name, spec in PHYSICAL_LAYERS.items() if spec.conductive)


def layer_name(layer: tuple[int, int]) -> str:
    for name, spec in PHYSICAL_LAYERS.items():
        if spec.layer == layer:
            return name
    return f"L{layer[0]}_{layer[1]}"

