"""Versioned superconducting process-design-kit models and YAML loading."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from textlayout._legacy.process import FabRules, LayerSpec, MaterialSpec, ProcessStack


_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _positive(name: str, value: float) -> float:
    value = float(value)
    if value <= 0.0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value


def _non_negative(name: str, value: float) -> float:
    value = float(value)
    if value < 0.0:
        raise ValueError(f"{name} must be non-negative, got {value}")
    return value


@dataclass(frozen=True)
class PDKMaterial:
    name: str
    kind: str
    relative_permittivity: float | None = None
    loss_tangent: float | None = None
    sheet_resistance_ohm: float | None = None
    critical_temperature_k: float | None = None
    penetration_depth_nm: float | None = None
    kinetic_inductance_ph_per_square: float = 0.0
    gap_frequency_ghz: float | None = None
    surface_resistance_microohm: float | None = None

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "PDKMaterial":
        material = cls(
            name=name,
            kind=str(data["kind"]),
            relative_permittivity=(
                float(data["relative_permittivity"])
                if data.get("relative_permittivity") is not None
                else None
            ),
            loss_tangent=(
                float(data["loss_tangent"]) if data.get("loss_tangent") is not None else None
            ),
            sheet_resistance_ohm=(
                float(data["sheet_resistance_ohm"])
                if data.get("sheet_resistance_ohm") is not None
                else None
            ),
            critical_temperature_k=(
                float(data["critical_temperature_k"])
                if data.get("critical_temperature_k") is not None
                else None
            ),
            penetration_depth_nm=(
                float(data["penetration_depth_nm"])
                if data.get("penetration_depth_nm") is not None
                else None
            ),
            kinetic_inductance_ph_per_square=float(
                data.get("kinetic_inductance_ph_per_square", 0.0)
            ),
            gap_frequency_ghz=(
                float(data["gap_frequency_ghz"])
                if data.get("gap_frequency_ghz") is not None
                else None
            ),
            surface_resistance_microohm=(
                float(data["surface_resistance_microohm"])
                if data.get("surface_resistance_microohm") is not None
                else None
            ),
        )
        _non_negative(
            f"materials.{name}.kinetic_inductance_ph_per_square",
            material.kinetic_inductance_ph_per_square,
        )
        for field_name in (
            "relative_permittivity",
            "critical_temperature_k",
            "penetration_depth_nm",
            "gap_frequency_ghz",
        ):
            value = getattr(material, field_name)
            if value is not None:
                _positive(f"materials.{name}.{field_name}", value)
        for field_name in ("loss_tangent", "sheet_resistance_ohm", "surface_resistance_microohm"):
            value = getattr(material, field_name)
            if value is not None:
                _non_negative(f"materials.{name}.{field_name}", value)
        return material

    def surface_impedance(self, frequency_hz: float) -> dict[str, float]:
        """Return the sheet surface impedance ``Rs + j*w*Ls`` in ohms/square."""
        frequency_hz = _positive("frequency_hz", frequency_hz)
        rs_ohm = (self.surface_resistance_microohm or 0.0) * 1e-6
        ls_h = self.kinetic_inductance_ph_per_square * 1e-12
        return {
            "frequency_hz": frequency_hz,
            "resistance_ohm_per_square": rs_ohm,
            "reactance_ohm_per_square": 2.0 * math.pi * frequency_hz * ls_h,
            "inductance_h_per_square": ls_h,
        }


@dataclass(frozen=True)
class PDKLayer:
    name: str
    gds_layer: int
    gds_datatype: int
    purpose: str
    material: str
    thickness_nm: float
    min_width_um: float
    min_spacing_um: float
    overlay_tolerance_um: float
    critical_current_density_ua_per_um2: float | None = None

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "PDKLayer":
        gds = data.get("gds")
        if not isinstance(gds, list) or len(gds) != 2:
            raise ValueError(f"layers.{name}.gds must be [layer, datatype]")
        layer = cls(
            name=name,
            gds_layer=int(gds[0]),
            gds_datatype=int(gds[1]),
            purpose=str(data["purpose"]),
            material=str(data["material"]),
            thickness_nm=float(data["thickness_nm"]),
            min_width_um=float(data["min_width_um"]),
            min_spacing_um=float(data["min_spacing_um"]),
            overlay_tolerance_um=float(data["overlay_tolerance_um"]),
            critical_current_density_ua_per_um2=(
                float(data["critical_current_density_ua_per_um2"])
                if data.get("critical_current_density_ua_per_um2") is not None
                else None
            ),
        )
        if layer.gds_layer < 0 or layer.gds_datatype < 0:
            raise ValueError(f"layers.{name}.gds values must be non-negative")
        _positive(f"layers.{name}.thickness_nm", layer.thickness_nm)
        _non_negative(f"layers.{name}.min_width_um", layer.min_width_um)
        _non_negative(f"layers.{name}.min_spacing_um", layer.min_spacing_um)
        _non_negative(f"layers.{name}.overlay_tolerance_um", layer.overlay_tolerance_um)
        if layer.critical_current_density_ua_per_um2 is not None:
            _positive(
                f"layers.{name}.critical_current_density_ua_per_um2",
                layer.critical_current_density_ua_per_um2,
            )
        return layer

    @property
    def gds(self) -> tuple[int, int]:
        return self.gds_layer, self.gds_datatype


@dataclass(frozen=True)
class FabricationConstraints:
    min_junction_width_um: float
    min_junction_height_um: float
    min_trace_width_um: float
    min_trace_spacing_um: float
    min_cpw_gap_um: float
    via_min_size_um: float
    via_enclosure_um: float
    overlay_tolerance_um: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FabricationConstraints":
        constraints = cls(**{field: float(data[field]) for field in cls.__dataclass_fields__})
        for name, value in asdict(constraints).items():
            _non_negative(f"constraints.{name}", value)
        return constraints


@dataclass(frozen=True)
class SuperconductingPDK:
    process_id: str
    name: str
    version: str
    status: str
    materials: dict[str, PDKMaterial]
    layers: dict[str, PDKLayer]
    constraints: FabricationConstraints
    provenance: dict[str, Any]
    source_path: str | None = None

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], *, source_path: str | Path | None = None
    ) -> "SuperconductingPDK":
        if data.get("schema") != "text-to-gds.superconducting-pdk.v1":
            raise ValueError("Unsupported or missing PDK schema")
        version = str(data["version"])
        if _VERSION_RE.fullmatch(version) is None:
            raise ValueError(f"version must use MAJOR.MINOR.PATCH, got {version!r}")
        materials = {
            name: PDKMaterial.from_dict(name, values)
            for name, values in dict(data["materials"]).items()
        }
        layers = {
            name: PDKLayer.from_dict(name, values)
            for name, values in dict(data["layers"]).items()
        }
        unknown_materials = sorted({layer.material for layer in layers.values()} - materials.keys())
        if unknown_materials:
            raise ValueError(f"Layers reference undefined materials: {unknown_materials}")
        gds_pairs = [layer.gds for layer in layers.values()]
        if len(gds_pairs) != len(set(gds_pairs)):
            raise ValueError("Each layer must have a unique GDS layer/datatype pair")
        return cls(
            process_id=str(data["process_id"]),
            name=str(data["name"]),
            version=version,
            status=str(data["status"]),
            materials=materials,
            layers=layers,
            constraints=FabricationConstraints.from_dict(dict(data["constraints"])),
            provenance=dict(data.get("provenance", {})),
            source_path=str(source_path) if source_path is not None else None,
        )

    @property
    def version_tuple(self) -> tuple[int, int, int]:
        return tuple(int(part) for part in self.version.split("."))  # type: ignore[return-value]

    def layer_for_gds(self, layer: int, datatype: int = 0) -> PDKLayer:
        for spec in self.layers.values():
            if spec.gds == (layer, datatype):
                return spec
        raise KeyError(f"No layer mapped to GDS ({layer}, {datatype})")

    def validate_geometry(
        self, layer_name: str, *, width_um: float, spacing_um: float | None = None
    ) -> list[str]:
        layer = self.layers[layer_name]
        violations = []
        if width_um < layer.min_width_um:
            violations.append(
                f"{layer_name} width {width_um:g} um is below {layer.min_width_um:g} um"
            )
        if spacing_um is not None and spacing_um < layer.min_spacing_um:
            violations.append(
                f"{layer_name} spacing {spacing_um:g} um is below {layer.min_spacing_um:g} um"
            )
        return violations

    def to_process_stack(self) -> ProcessStack:
        """Adapt a loaded PDK to the package's existing layout process model."""
        layers = {
            name: LayerSpec(
                name=name,
                layer=spec.gds,
                purpose=spec.purpose,
                material=spec.material,
                thickness_nm=spec.thickness_nm,
                min_width_um=spec.min_width_um,
                min_spacing_um=spec.min_spacing_um,
            )
            for name, spec in self.layers.items()
        }
        materials = {
            name: MaterialSpec(
                name=name,
                conductivity_s_per_m=None,
                relative_permittivity=spec.relative_permittivity,
                kinetic_inductance_ph_per_square=spec.kinetic_inductance_ph_per_square,
                critical_temperature_k=spec.critical_temperature_k,
                notes=f"Loaded from {self.process_id} PDK version {self.version}.",
            )
            for name, spec in self.materials.items()
        }
        c = self.constraints
        return ProcessStack(
            name=f"{self.process_id}@{self.version}",
            layers=layers,
            materials=materials,
            rules=FabRules(
                min_junction_width_um=c.min_junction_width_um,
                min_junction_height_um=c.min_junction_height_um,
                min_trace_width_um=c.min_trace_width_um,
                min_trace_spacing_um=c.min_trace_spacing_um,
                min_cpw_gap_um=c.min_cpw_gap_um,
                via_min_size_um=c.via_min_size_um,
                via_enclosure_um=c.via_enclosure_um,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_pdk(path: str | Path) -> SuperconductingPDK:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"PDK file must contain a YAML mapping: {path}")
    return SuperconductingPDK.from_dict(data, source_path=path)


class PDKDatabase:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def list(self) -> list[SuperconductingPDK]:
        return [load_pdk(path) for path in sorted(self.root.glob("*.yaml"))]

    def get(self, process_id: str, version: str | None = None) -> SuperconductingPDK:
        candidates = [pdk for pdk in self.list() if pdk.process_id == process_id]
        if version is not None:
            candidates = [pdk for pdk in candidates if pdk.version == version]
        if not candidates:
            suffix = f" at version {version}" if version else ""
            raise KeyError(f"Unknown PDK {process_id!r}{suffix}")
        return max(candidates, key=lambda pdk: pdk.version_tuple)


from textlayout._legacy.pdk.layer_stack import DEFAULT_LAYER_MAP, DEFAULT_LAYER_STACK, LayerMap, QuantumLayerStack  # noqa: E402
from textlayout._legacy.pdk.layers import CONDUCTIVE_LAYER_NAMES, PHYSICAL_LAYERS, PhysicalLayer  # noqa: E402
from textlayout._legacy.pdk.materials import DEFAULT_MATERIAL_CATALOG, MaterialCatalog  # noqa: E402
from textlayout._legacy.pdk.process import DEFAULT_MANHATTAN_PROCESS, ManhattanProcess  # noqa: E402
from textlayout._legacy.pdk.rules import DEFAULT_FABRICATION_RULES, FabricationRuleSet  # noqa: E402
from textlayout._legacy.pdk.technology import DEFAULT_TECHNOLOGY, QuantumTechnology, load_quantum_technology  # noqa: E402

__all__ = [
    "DEFAULT_FABRICATION_RULES",
    "DEFAULT_LAYER_MAP",
    "DEFAULT_LAYER_STACK",
    "DEFAULT_MANHATTAN_PROCESS",
    "DEFAULT_MATERIAL_CATALOG",
    "DEFAULT_TECHNOLOGY",
    "CONDUCTIVE_LAYER_NAMES",
    "FabricationConstraints",
    "FabricationRuleSet",
    "LayerMap",
    "ManhattanProcess",
    "MaterialCatalog",
    "PDKDatabase",
    "PDKLayer",
    "PDKMaterial",
    "PHYSICAL_LAYERS",
    "PhysicalLayer",
    "QuantumLayerStack",
    "QuantumTechnology",
    "SuperconductingPDK",
    "load_pdk",
    "load_quantum_technology",
]
