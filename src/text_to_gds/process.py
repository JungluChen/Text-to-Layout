from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TypeAlias

Layer: TypeAlias = tuple[int, int]


@dataclass(frozen=True)
class LayerSpec:
    """Physical/process meaning for one GDS layer/datatype pair."""

    name: str
    layer: Layer
    purpose: str
    material: str
    thickness_nm: float
    min_width_um: float
    min_spacing_um: float


@dataclass(frozen=True)
class MaterialSpec:
    """Compact material model used for planning and first-order estimates."""

    name: str
    conductivity_s_per_m: float | None
    relative_permittivity: float | None
    kinetic_inductance_ph_per_square: float
    critical_temperature_k: float | None
    notes: str


@dataclass(frozen=True)
class FabRules:
    min_junction_width_um: float
    min_junction_height_um: float
    min_trace_width_um: float
    min_trace_spacing_um: float
    min_cpw_gap_um: float
    via_min_size_um: float
    via_enclosure_um: float


@dataclass(frozen=True)
class ProcessStack:
    name: str
    layers: dict[str, LayerSpec]
    materials: dict[str, MaterialSpec]
    rules: FabRules

    def layer(self, name: str) -> Layer:
        return self.layers[name].layer

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


DEFAULT_MATERIALS: dict[str, MaterialSpec] = {
    "Nb": MaterialSpec(
        name="Nb",
        conductivity_s_per_m=None,
        relative_permittivity=None,
        kinetic_inductance_ph_per_square=0.10,
        critical_temperature_k=9.2,
        notes="Default niobium superconductor placeholder; replace with measured film data.",
    ),
    "AlOx": MaterialSpec(
        name="AlOx",
        conductivity_s_per_m=None,
        relative_permittivity=9.0,
        kinetic_inductance_ph_per_square=0.0,
        critical_temperature_k=None,
        notes="Tunnel-barrier dielectric placeholder for SIS junction estimates.",
    ),
    "Si": MaterialSpec(
        name="Si",
        conductivity_s_per_m=None,
        relative_permittivity=11.45,
        kinetic_inductance_ph_per_square=0.0,
        critical_temperature_k=None,
        notes="High-resistivity silicon substrate placeholder.",
    ),
}


DEFAULT_LAYERS: dict[str, LayerSpec] = {
    "M1": LayerSpec(
        name="M1",
        layer=(3, 0),
        purpose="bottom electrode and local interconnect",
        material="Nb",
        thickness_nm=180.0,
        min_width_um=0.20,
        min_spacing_um=0.20,
    ),
    "JJ": LayerSpec(
        name="JJ",
        layer=(4, 0),
        purpose="Josephson tunnel barrier",
        material="AlOx",
        thickness_nm=2.0,
        min_width_um=0.10,
        min_spacing_um=0.20,
    ),
    "M2": LayerSpec(
        name="M2",
        layer=(5, 0),
        purpose="top electrode and local routing",
        material="Nb",
        thickness_nm=200.0,
        min_width_um=0.20,
        min_spacing_um=0.20,
    ),
    "M3": LayerSpec(
        name="M3",
        layer=(6, 0),
        purpose="global microwave routing",
        material="Nb",
        thickness_nm=350.0,
        min_width_um=0.50,
        min_spacing_um=0.50,
    ),
    "VIA12": LayerSpec(
        name="VIA12",
        layer=(7, 0),
        purpose="M1 to M2 via",
        material="Nb",
        thickness_nm=200.0,
        min_width_um=0.30,
        min_spacing_um=0.30,
    ),
    "VIA23": LayerSpec(
        name="VIA23",
        layer=(8, 0),
        purpose="M2 to M3 via",
        material="Nb",
        thickness_nm=250.0,
        min_width_um=0.40,
        min_spacing_um=0.40,
    ),
    "MARKER": LayerSpec(
        name="MARKER",
        layer=(10, 0),
        purpose="labels and non-fab annotations",
        material="Si",
        thickness_nm=0.0,
        min_width_um=0.0,
        min_spacing_um=0.0,
    ),
}


DEFAULT_RULES = FabRules(
    min_junction_width_um=0.10,
    min_junction_height_um=0.10,
    min_trace_width_um=0.20,
    min_trace_spacing_um=0.20,
    min_cpw_gap_um=1.00,
    via_min_size_um=0.30,
    via_enclosure_um=0.20,
)

DEFAULT_PROCESS = ProcessStack(
    name="generic_nb_3metal_sis_v0",
    layers=DEFAULT_LAYERS,
    materials=DEFAULT_MATERIALS,
    rules=DEFAULT_RULES,
)

M1 = DEFAULT_PROCESS.layer("M1")
JJ = DEFAULT_PROCESS.layer("JJ")
M2 = DEFAULT_PROCESS.layer("M2")
M3 = DEFAULT_PROCESS.layer("M3")
VIA12 = DEFAULT_PROCESS.layer("VIA12")
VIA23 = DEFAULT_PROCESS.layer("VIA23")
MARKER = DEFAULT_PROCESS.layer("MARKER")


def require_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")


def require_minimum(name: str, value: float, minimum: float) -> None:
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum:g} um, got {value:g} um")


def layer_to_list(layer: Layer) -> list[int]:
    return [int(layer[0]), int(layer[1])]
