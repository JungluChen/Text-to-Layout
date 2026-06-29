"""EDA-style quantum component abstractions and public component classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import gdsfactory as gf


@dataclass(frozen=True)
class QuantumPort:
    name: str
    center_um: tuple[float, float]
    width_um: float
    orientation_deg: float
    layer: tuple[int, int]
    kind: str = "electrical"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "center_um": [self.center_um[0], self.center_um[1]],
            "width_um": self.width_um,
            "orientation_deg": self.orientation_deg,
            "layer": [self.layer[0], self.layer[1]],
            "kind": self.kind,
        }


@dataclass(frozen=True)
class ComponentNet:
    name: str
    ports: tuple[str, ...]
    kind: str = "electrical"

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ports": list(self.ports), "kind": self.kind}


@dataclass(frozen=True)
class ComponentNetlist:
    component: str
    nets: tuple[ComponentNet, ...]
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "text-to-gds.component-netlist.v1",
            "component": self.component,
            "nets": [net.to_dict() for net in self.nets],
            "parameters": self.parameters,
        }


@dataclass(frozen=True)
class RefPoint:
    """KQCircuits-style named geometric reference point."""

    name: str
    center_um: tuple[float, float]
    role: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "center_um": list(self.center_um), "role": self.role}


class QuantumComponent(ABC):
    """Base class for components with explicit EDA lifecycle methods."""

    name: str

    @abstractmethod
    def geometry(self) -> gf.Component:
        """Return GDS-ready component geometry."""

    @abstractmethod
    def ports(self) -> dict[str, QuantumPort]:
        """Return named ports with physical locations and layers."""

    def refpoints(self) -> dict[str, RefPoint]:
        """Return named KQCircuits-style reference points."""
        return {}

    @abstractmethod
    def netlist(self) -> ComponentNetlist:
        """Return component-level electrical connectivity."""

    @abstractmethod
    def extract(self) -> dict[str, Any]:
        """Return physical parameters derived from explicit geometry/process inputs."""

    def simulation_ports(self) -> dict[str, QuantumPort]:
        """Return ports intended for EM/circuit simulation."""
        return self.ports()

    def validation_rules(self) -> dict[str, Any]:
        """Return component-specific validation hints."""
        return {"requires_ports": True, "requires_lvs": True}

    def simulate(self, *, output_dir: str | Path | None = None) -> dict[str, Any]:
        """Return an honest simulation status."""
        return {
            "schema": "text-to-gds.component-simulation.v1",
            "component": self.name,
            "status": "skipped",
            "reason": "solver not executed",
            "output_dir": str(output_dir) if output_dir else None,
        }


class MicrowaveComponent(QuantumComponent):
    """Marker base for microwave components such as CPWs, launchers, and resonators."""


class JosephsonComponent(QuantumComponent):
    """Marker base for Josephson components with junction extraction."""

