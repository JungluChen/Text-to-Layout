from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path as _Path

from textlayout._paths import resource_path
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
        purpose="ground plane, bottom electrode, and local interconnect",
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
        purpose="CPW center trace, top electrode, and local routing",
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
    "UNDERCUT": LayerSpec(
        name="UNDERCUT",
        layer=(9, 0),
        purpose="junction undercut region",
        material="air",
        thickness_nm=0.0,
        min_width_um=0.10,
        min_spacing_um=0.10,
    ),
    "MARKER": LayerSpec(
        name="MARKER",
        layer=(10, 0),
        purpose="labels, extraction markers, and non-fab annotations",
        material="Si",
        thickness_nm=0.0,
        min_width_um=0.0,
        min_spacing_um=0.0,
    ),
    "CHIP_BOUNDARY": LayerSpec(
        name="CHIP_BOUNDARY",
        layer=(11, 0),
        purpose="substrate die outline and chip boundary",
        material="Si",
        thickness_nm=0.0,
        min_width_um=0.0,
        min_spacing_um=0.0,
    ),
    "KEEPOUT": LayerSpec(
        name="KEEPOUT",
        layer=(12, 0),
        purpose="wirebond, airbridge, package, and DRC exclusion region",
        material="air",
        thickness_nm=0.0,
        min_width_um=0.0,
        min_spacing_um=0.0,
    ),
    "PORT": LayerSpec(
        name="PORT",
        layer=(13, 0),
        purpose="RF/DC port marker and measurement reference",
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
UNDERCUT = DEFAULT_PROCESS.layer("UNDERCUT")
MARKER = DEFAULT_PROCESS.layer("MARKER")
CHIP_BOUNDARY = DEFAULT_PROCESS.layer("CHIP_BOUNDARY")
KEEPOUT = DEFAULT_PROCESS.layer("KEEPOUT")
PORT = DEFAULT_PROCESS.layer("PORT")


def require_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")


def require_minimum(name: str, value: float, minimum: float) -> None:
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum:g} um, got {value:g} um")


def layer_to_list(layer: Layer) -> list[int]:
    return [int(layer[0]), int(layer[1])]


# ---------------------------------------------------------------------------
# Technology YAML loader
# ---------------------------------------------------------------------------

_BUILTIN_PROCESS_DIR = resource_path("process")
_FALLBACK_PROCESS_DIRS: list[_Path] = [
    _BUILTIN_PROCESS_DIR,
    _Path(__file__).parent / "process",
]


def find_technology_yaml(tech_id: str, extra_dirs: list[_Path] | None = None) -> _Path | None:
    """Search for a technology YAML file matching *tech_id*.

    Looks in (in order):
      1. ``extra_dirs`` if supplied
      2. ``<repo_root>/process/``
      3. ``<package>/process/``

    Returns the first matching path or None if not found.
    """
    slug = tech_id.lower().replace("-", "_").replace(" ", "_")
    search = list(extra_dirs or []) + _FALLBACK_PROCESS_DIRS
    for directory in search:
        for candidate in (
            directory / f"{slug}.yaml",
            directory / f"{tech_id}.yaml",
        ):
            if candidate.is_file():
                return candidate
    return None


def load_technology_yaml(tech_id: str, extra_dirs: list[_Path] | None = None) -> ProcessStack:
    """Load a ProcessStack from a technology YAML file.

    Raises FileNotFoundError when no YAML matching *tech_id* can be found.
    Use ``find_technology_yaml`` to check existence first.
    """
    path = find_technology_yaml(tech_id, extra_dirs)
    if path is None:
        searched = [str(d) for d in (list(extra_dirs or []) + _FALLBACK_PROCESS_DIRS)]
        raise FileNotFoundError(
            f"No technology YAML found for '{tech_id}'. "
            f"Searched: {searched}. "
            "Add a YAML file to the process/ directory or pass extra_dirs."
        )
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        raise ImportError(
            "PyYAML is required to load technology files. "
            "Run: pip install pyyaml"
        ) from None

    data: dict = yaml.safe_load(path.read_text(encoding="utf-8"))

    layers_raw: dict = data.get("layers", {})
    materials_raw: dict = data.get("materials", {})
    constraints_raw: dict = data.get("constraints", {})

    materials: dict[str, MaterialSpec] = {}
    for name, m in materials_raw.items():
        materials[name] = MaterialSpec(
            name=name,
            conductivity_s_per_m=m.get("conductivity_s_per_m"),
            relative_permittivity=m.get("relative_permittivity"),
            kinetic_inductance_ph_per_square=float(m.get("kinetic_inductance_ph_per_square", 0.0)),
            critical_temperature_k=m.get("critical_temperature_k"),
            notes=str(m.get("notes", "")),
        )
    if not materials:
        materials = dict(DEFAULT_MATERIALS)

    layers: dict[str, LayerSpec] = {}
    for name, lspec in layers_raw.items():
        gds = lspec.get("gds", [0, 0])
        layers[name] = LayerSpec(
            name=name,
            layer=(int(gds[0]), int(gds[1])),
            purpose=str(lspec.get("purpose", "")),
            material=str(lspec.get("material", "unknown")),
            thickness_nm=float(lspec.get("thickness_nm", 0.0)),
            min_width_um=float(lspec.get("min_width_um", 0.0)),
            min_spacing_um=float(lspec.get("min_spacing_um", 0.0)),
        )
    if not layers:
        layers = dict(DEFAULT_LAYERS)

    rules = FabRules(
        min_junction_width_um=float(constraints_raw.get("min_junction_width_um", DEFAULT_RULES.min_junction_width_um)),
        min_junction_height_um=float(constraints_raw.get("min_junction_height_um", DEFAULT_RULES.min_junction_height_um)),
        min_trace_width_um=float(constraints_raw.get("min_trace_width_um", DEFAULT_RULES.min_trace_width_um)),
        min_trace_spacing_um=float(constraints_raw.get("min_trace_spacing_um", DEFAULT_RULES.min_trace_spacing_um)),
        min_cpw_gap_um=float(constraints_raw.get("min_cpw_gap_um", DEFAULT_RULES.min_cpw_gap_um)),
        via_min_size_um=float(constraints_raw.get("via_min_size_um", DEFAULT_RULES.via_min_size_um)),
        via_enclosure_um=float(constraints_raw.get("via_enclosure_um", DEFAULT_RULES.via_enclosure_um)),
    )

    name = str(data.get("name", tech_id))
    return ProcessStack(name=name, layers=layers, materials=materials, rules=rules)
