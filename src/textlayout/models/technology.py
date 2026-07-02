"""Technology / layer-stack domain entities.

A :class:`Technology` is an immutable description of a fabrication process: the
named layers, their GDS layer/datatype numbers, the manufacturing grid, and the
minimum-spacing design rules. Generators receive a ``Technology`` and translate
abstract layer names (``"M1"``) into concrete geometry; exporters use it to map
layer names to GDS layer numbers.

The *entity* lives in the domain layer; concrete *instances* (the generic stack,
or a PDK loaded from disk) live in the ``knowledge`` layer. This keeps the domain
free of process data.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class LayerInfo:
    """A single fabrication layer."""

    name: str
    gds_layer: int
    gds_datatype: int = 0
    description: str = ""
    color: str = "#888888"
    """Hex colour used by visual exporters (e.g. SVG preview)."""


@dataclass(frozen=True, slots=True)
class Technology:
    """An immutable fabrication-process description."""

    name: str
    layers: Mapping[str, LayerInfo]
    grid_nm: float = 1.0
    """Manufacturing grid in nanometres; geometry should snap to this."""
    default_min_spacing_um: float = 1.0
    min_spacing_um: Mapping[str, float] = field(default_factory=dict)
    default_min_width_um: float = 1.0
    min_width_um: Mapping[str, float] = field(default_factory=dict)
    substrate_epsilon_r: float = 11.9
    """Relative permittivity of the substrate (default: high-resistivity silicon)."""

    def has_layer(self, name: str) -> bool:
        return name in self.layers

    def layer(self, name: str) -> LayerInfo:
        try:
            return self.layers[name]
        except KeyError as exc:
            raise KeyError(
                f"Layer {name!r} not in technology {self.name!r}; have {sorted(self.layers)}"
            ) from exc

    def min_spacing_for(self, layer: str) -> float:
        return self.min_spacing_um.get(layer, self.default_min_spacing_um)

    def min_width_for(self, layer: str) -> float:
        return self.min_width_um.get(layer, self.default_min_width_um)

    @property
    def grid_um(self) -> float:
        return self.grid_nm / 1000.0
