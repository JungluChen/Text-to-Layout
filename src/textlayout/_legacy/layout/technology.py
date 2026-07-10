"""Technology abstraction for layout backends (gdsfactory, KQCircuits)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PCellSelector(Protocol):
    """Protocol for selecting and instantiating PCells from a layout backend."""

    backend: str

    def has_pcell(self, name: str) -> bool: ...

    def create_pcell(self, name: str, parameters: dict[str, Any]) -> Any: ...

    def supported_pcells(self) -> list[str]: ...


@dataclass(frozen=True)
class SuperconductingTechnology:
    """Describes a technology stack for superconducting layout generation."""

    name: str
    backend: str
    process_id: str
    pdk_path: str | None = None
    extra_params: dict[str, Any] = field(default_factory=dict)

    def selector(self) -> PCellSelector:
        return TechnologyFactory.create(self.backend)


class KQCircuitsSelector:
    """PCell selector backed by KQCircuits."""

    backend = "kqcircuits"

    _CELLS = {
        "cpw_straight",
        "cpw_quarter_wave_resonator",
        "cpw_taper",
        "cross_taper",
        "ground_plane",
        "junction",
        "meander",
    }

    def has_pcell(self, name: str) -> bool:
        return name in self._CELLS

    def create_pcell(self, name: str, parameters: dict[str, Any]) -> dict[str, Any]:
        if not self.has_pcell(name):
            raise KeyError(f"Unknown KQCircuits PCell: {name}")
        return {"backend": self.backend, "cell": name, "params": parameters}

    def supported_pcells(self) -> list[str]:
        return sorted(self._CELLS)


class GDSFactorySelector:
    """PCell selector backed by gdsfactory."""

    backend = "gdsfactory"

    _CELLS = {
        "straight",
        "bend_euler",
        "cross",
        "rectangle",
        "circle",
        "polygon",
        "pack",
    }

    def has_pcell(self, name: str) -> bool:
        return name in self._CELLS

    def create_pcell(self, name: str, parameters: dict[str, Any]) -> dict[str, Any]:
        if not self.has_pcell(name):
            raise KeyError(f"Unknown gdsfactory PCell: {name}")
        return {"backend": self.backend, "cell": name, "params": parameters}

    def supported_pcells(self) -> list[str]:
        return sorted(self._CELLS)


class TechnologyFactory:
    """Creates the correct PCellSelector for a given backend string."""

    _BACKENDS: dict[str, type] = {
        "kqcircuits": KQCircuitsSelector,
        "gdsfactory": GDSFactorySelector,
    }

    @classmethod
    def create(cls, backend: str) -> PCellSelector:
        klass = cls._BACKENDS.get(backend)
        if klass is None:
            raise ValueError(
                f"Unknown backend {backend!r}. "
                f"Available: {sorted(cls._BACKENDS)}"
            )
        return klass()

    @classmethod
    def register(cls, backend: str, selector_class: type) -> None:
        cls._BACKENDS[backend] = selector_class
