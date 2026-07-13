"""A typed 3-D finite-element model: volumes, surfaces, interfaces, ports, mesh.

The Palace configuration was hand-written JSON, and the Gmsh physical groups were
integers chosen at the call site. Nothing tied the two together, so a mesh whose
outer boundary was tagged ``2`` and a config whose ``Boundaries.PEC`` said ``[1]``
were both individually valid and jointly meaningless -- Palace would solve a
cavity with no walls, or short an internal interface and return the eigenmode of
a different structure. That second failure happened while this repository's first
Palace benchmark was being built: making the shared interface PEC split the cavity
in two and moved the fundamental from 6.00 GHz to 7.07 GHz. Nothing detected it
except a physicist noticing the number was wrong.

:class:`FEMModel` is the one place attributes are assigned. Gmsh physical groups
and the Palace configuration are both *projections* of it, so they cannot
disagree. The model validates what a solver cannot: that every volume names a
material that exists, that an interface separates two volumes that exist, that no
attribute is reused across volumes, and that a bounded eigenmode problem has a
boundary at all.

Surfaces carry an explicit ``kind``. An interface between two volumes is *not* a
boundary condition and may never be tagged PEC by accident: it is declared as an
:class:`Interface`, which knows the two volumes it separates.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FEM_MODEL_SCHEMA = "textlayout.fem-model.v1"

#: What a volume is *for*. Drives EPR region assignment downstream: a
#: participation ratio is meaningless unless the regions are named physically.
VolumeRole = Literal[
    "substrate",
    "vacuum",
    "package",
    "metal_bulk",
    "junction_dielectric",
    "lossy_interface",
    "custom",
]

#: How a surface acts electromagnetically.
SurfaceKind = Literal[
    "pec",  # perfect electric conductor: superconducting metal, or a cavity wall
    "pmc_symmetry",  # perfect magnetic conductor: a symmetry plane
    "absorbing",  # first/second-order radiation boundary
    "impedance",  # surface impedance (finite conductivity, thin metal)
]

SurfaceRole = Literal[
    "superconducting_metal",
    "package_wall",
    "lid",
    "symmetry",
    "port",
    "external",
    "custom",
]

MeshRegionKind = Literal[
    "conductor_edge",
    "cpw_gap",
    "coupler_gap",
    "open_end",
    "grounded_end",
    "dielectric_interface",
    "custom",
]

CriticalRegionType = Literal["volume", "surface", "near_field"]

CriticalRegionKind = Literal[
    "left_cpw_gap",
    "right_cpw_gap",
    "cpw_gap",
    "coupling_gap",
    "resonator_open_end",
    "resonator_grounded_end",
    "substrate_vacuum_interface",
    "metal_substrate_interface",
    "metal_air_interface",
    "junction_near_field",
    "user_defined_high_field",
    # Compatibility values retained for existing serialized models.
    "resonator_end",
    "substrate_interface",
    "junction",
]


class FEMModelError(ValueError):
    """The model is not solvable, and saying so now beats a wrong eigenvalue."""


class Material(BaseModel):
    """A linear isotropic medium. Loss is optional and separately labelled."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    permittivity: float = Field(gt=0)
    permeability: float = Field(gt=0, default=1.0)
    loss_tangent: float = Field(ge=0, default=0.0)

    @model_validator(mode="after")
    def _finite(self) -> Material:
        for field in ("permittivity", "permeability", "loss_tangent"):
            if not math.isfinite(getattr(self, field)):
                raise FEMModelError(f"material {self.name!r}: {field} must be finite")
        return self


class Volume(BaseModel):
    """A 3-D region, its mesh attribute, and the material filling it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    attribute: int = Field(ge=1, description="Gmsh physical-group tag for this volume.")
    material: str = Field(min_length=1)
    role: VolumeRole = "custom"
    #: Request per-region field energy from the solver. Without this the volume
    #: contributes to the solution but no participation can be extracted from it.
    postprocess_energy: bool = False


class Surface(BaseModel):
    """A 2-D region carrying a boundary condition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    attribute: int = Field(ge=1)
    kind: SurfaceKind
    role: SurfaceRole = "custom"
    #: Surface resistance in ohm/square, for ``kind='impedance'`` only.
    resistance_ohm_per_square: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _impedance_needs_resistance(self) -> Surface:
        if self.kind == "impedance" and self.resistance_ohm_per_square is None:
            raise FEMModelError(
                f"surface {self.name!r}: kind='impedance' requires "
                "resistance_ohm_per_square; a lossy sheet with no loss is a PEC"
            )
        if self.kind != "impedance" and self.resistance_ohm_per_square is not None:
            raise FEMModelError(
                f"surface {self.name!r}: resistance_ohm_per_square is meaningless "
                f"for kind={self.kind!r}"
            )
        return self


class MeshRegion(BaseModel):
    """A named geometric selection used only to control local mesh size."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    kind: MeshRegionKind
    dimension: Literal[0, 1, 2, 3]


class CriticalRegion(BaseModel):
    """Declared high-field geometry that must be independently coverable.

    Volume regions participate in material-weighted volume integration. Surface
    regions name 2-D physical entities such as metal-substrate interfaces; they
    are not represented as fake lossy volumes. Near-field regions name bounded
    geometric selections used for mesh/refinement and postprocessing.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    kind: CriticalRegionKind
    region_type: CriticalRegionType = "volume"
    attribute_ids: list[int] = Field(
        default_factory=list,
        description="Compatibility alias for volume_attribute_ids.",
    )
    volume_attribute_ids: list[int] = Field(default_factory=list)
    surface_attribute_ids: list[int] = Field(default_factory=list)
    mesh_region_names: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _target_matches_region_type(self) -> CriticalRegion:
        volume_ids = list(self.volume_attribute_ids or self.attribute_ids)
        if self.region_type == "volume":
            if not volume_ids:
                raise FEMModelError(
                    f"critical volume region {self.name!r} needs volume_attribute_ids"
                )
            if self.surface_attribute_ids or self.mesh_region_names:
                raise FEMModelError(
                    f"critical volume region {self.name!r} may not target surfaces "
                    "or near-field mesh regions"
                )
        elif self.region_type == "surface":
            if not self.surface_attribute_ids:
                raise FEMModelError(
                    f"critical surface region {self.name!r} needs surface_attribute_ids"
                )
            if volume_ids or self.mesh_region_names:
                raise FEMModelError(
                    f"critical surface region {self.name!r} may not be represented "
                    "as a volume or near-field region"
                )
        elif self.region_type == "near_field":
            if not self.mesh_region_names:
                raise FEMModelError(
                    f"critical near-field region {self.name!r} needs mesh_region_names"
                )
            if volume_ids or self.surface_attribute_ids:
                raise FEMModelError(
                    f"critical near-field region {self.name!r} may not target "
                    "volume or surface attributes"
                )
        return self

    @property
    def volume_ids(self) -> tuple[int, ...]:
        return tuple(self.volume_attribute_ids or self.attribute_ids)


class Interface(BaseModel):
    """A thin lossy layer between two volumes, modelled as a surface.

    Metal-substrate, substrate-air and metal-air interfaces are nanometres thick
    and cannot be meshed as volumes at device scale. They are declared here so an
    EPR calculation can attribute energy to them -- and so that nothing tags them
    as a boundary condition, which would short the structure.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    attribute: int = Field(ge=1)
    between: tuple[str, str] = Field(description="The two volume names this separates.")
    thickness_nm: float = Field(gt=0)
    permittivity: float = Field(gt=0)
    loss_tangent: float = Field(ge=0)

    @model_validator(mode="after")
    def _distinct(self) -> Interface:
        if self.between[0] == self.between[1]:
            raise FEMModelError(
                f"interface {self.name!r} separates {self.between[0]!r} from itself"
            )
        return self


class LumpedPort(BaseModel):
    """A lumped element port across a gap."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    index: int = Field(ge=1)
    attribute: int = Field(ge=1)
    impedance_ohm: float = Field(gt=0, default=50.0)
    direction: Literal["+X", "-X", "+Y", "-Y", "+Z", "-Z"]


class WavePort(BaseModel):
    """A numeric wave port solved as a 2-D eigenproblem on its own cross-section."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    index: int = Field(ge=1)
    attribute: int = Field(ge=1)
    mode_count: int = Field(ge=1, default=1)


class LocalRefinement(BaseModel):
    """Mesh size near a named entity, for fields that a global size cannot resolve.

    The field at a conductor edge is singular. A uniform characteristic length
    that resolves it would need an unaffordable element count everywhere else,
    which is why a CPW gap must be refined by name rather than globally.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: str = Field(min_length=1, description="Name of a surface, interface or volume.")
    characteristic_length: float = Field(gt=0)
    growth_distance: float = Field(
        gt=0, description="Distance over which the size relaxes to the global length."
    )


class MeshControl(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    characteristic_length: float = Field(gt=0, description="Global mesh size, in L0 units.")
    refinements: list[LocalRefinement] = Field(default_factory=list)
    #: Minimum permitted element quality; a mesh below this is not solved.
    min_element_quality: float = Field(default=0.0, ge=0.0, le=1.0)

    def scaled(self, factor: float) -> MeshControl:
        """A uniformly refined copy. Every length scales, so levels stay nested."""
        if not factor > 0:
            raise FEMModelError(f"refinement factor must be positive, got {factor!r}")
        return MeshControl(
            characteristic_length=self.characteristic_length * factor,
            refinements=[
                LocalRefinement(
                    target=r.target,
                    characteristic_length=r.characteristic_length * factor,
                    growth_distance=r.growth_distance,
                )
                for r in self.refinements
            ],
            min_element_quality=self.min_element_quality,
        )


class EigenmodeSolve(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode_count: int = Field(ge=1, default=2)
    target_frequency_ghz: float = Field(gt=0)
    tolerance: float = Field(gt=0, default=1e-10)
    element_order: int = Field(ge=1, le=4, default=1)
    linear_tolerance: float = Field(gt=0, default=1e-10)
    linear_max_iterations: int = Field(ge=1, default=1000)

    @property
    def formal_order(self) -> float:
        """Eigenvalue convergence order for Nedelec elements of order p is 2p."""
        return 2.0 * self.element_order


class FEMModel(BaseModel):
    """The complete solvable description. Attributes are assigned exactly here."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=FEM_MODEL_SCHEMA)
    name: str = Field(min_length=1)
    #: Metres per model length unit. 1e-3 means the mesh is in millimetres.
    length_unit_m: float = Field(gt=0, default=1e-6)

    materials: list[Material]
    volumes: list[Volume]
    surfaces: list[Surface]
    interfaces: list[Interface] = Field(default_factory=list)
    lumped_ports: list[LumpedPort] = Field(default_factory=list)
    wave_ports: list[WavePort] = Field(default_factory=list)
    mesh_regions: list[MeshRegion] = Field(default_factory=list)
    critical_regions: list[CriticalRegion] = Field(default_factory=list)
    mesh: MeshControl
    eigenmode: EigenmodeSolve

    @model_validator(mode="after")
    def _coherent(self) -> FEMModel:
        if not self.volumes:
            raise FEMModelError("a finite-element model needs at least one volume")

        known_materials = {material.name for material in self.materials}
        if len(known_materials) != len(self.materials):
            raise FEMModelError("material names must be unique")
        for volume in self.volumes:
            if volume.material not in known_materials:
                raise FEMModelError(
                    f"volume {volume.name!r} names material {volume.material!r}, "
                    f"which is not defined"
                )

        self._unique("volume", [v.attribute for v in self.volumes])
        volume_attributes = {v.attribute for v in self.volumes}
        critical_attributes = {
            attribute
            for region in self.critical_regions
            for attribute in region.volume_ids
        }
        unknown_critical = sorted(critical_attributes - volume_attributes)
        if unknown_critical:
            raise FEMModelError(
                "critical-region attributes must name model volumes; unknown: "
                f"{unknown_critical}"
            )
        # Surfaces, interfaces and ports all live on 2-D entities and therefore
        # share one attribute space. A port that reused an interface's tag would
        # silently overwrite it in the mesh.
        self._unique(
            "surface/interface/port",
            [s.attribute for s in self.surfaces]
            + [i.attribute for i in self.interfaces]
            + [p.attribute for p in self.lumped_ports]
            + [p.attribute for p in self.wave_ports],
        )

        volume_names = {volume.name for volume in self.volumes}
        for interface in self.interfaces:
            for side in interface.between:
                if side not in volume_names:
                    raise FEMModelError(
                        f"interface {interface.name!r} separates unknown volume {side!r}"
                    )

        surface_attributes = (
            {s.attribute for s in self.surfaces}
            | {i.attribute for i in self.interfaces}
            | {p.attribute for p in self.lumped_ports}
            | {p.attribute for p in self.wave_ports}
        )
        critical_surface_attributes = {
            attribute
            for region in self.critical_regions
            for attribute in region.surface_attribute_ids
        }
        unknown_critical_surfaces = sorted(critical_surface_attributes - surface_attributes)
        if unknown_critical_surfaces:
            raise FEMModelError(
                "critical surface-region attributes must name model surfaces, "
                f"interfaces or ports; unknown: {unknown_critical_surfaces}"
            )

        indices = [p.index for p in self.lumped_ports] + [p.index for p in self.wave_ports]
        if len(set(indices)) != len(indices):
            raise FEMModelError("port indices must be unique across lumped and wave ports")

        if not any(surface.kind in ("pec", "absorbing", "impedance") for surface in self.surfaces):
            raise FEMModelError(
                "an eigenmode problem needs a bounding surface (pec, absorbing or "
                "impedance); a domain with only symmetry planes is unbounded"
            )

        entity_names = (
            volume_names
            | {s.name for s in self.surfaces}
            | {i.name for i in self.interfaces}
            | {region.name for region in self.mesh_regions}
        )
        if len({region.name for region in self.mesh_regions}) != len(self.mesh_regions):
            raise FEMModelError("mesh-region names must be unique")
        for refinement in self.mesh.refinements:
            if refinement.target not in entity_names:
                raise FEMModelError(
                    f"mesh refinement targets unknown entity {refinement.target!r}"
                )
        mesh_region_names = {region.name for region in self.mesh_regions}
        critical_near_field_regions = {
            name for region in self.critical_regions for name in region.mesh_region_names
        }
        unknown_near_field = sorted(critical_near_field_regions - mesh_region_names)
        if unknown_near_field:
            raise FEMModelError(
                "critical near-field regions must name mesh regions; unknown: "
                f"{unknown_near_field}"
            )
        return self

    @property
    def critical_region_attributes(self) -> set[int]:
        return {
            attribute
            for region in self.critical_regions
            for attribute in region.volume_ids
        }

    @property
    def critical_surface_attributes(self) -> set[int]:
        return {
            attribute
            for region in self.critical_regions
            for attribute in region.surface_attribute_ids
        }

    @property
    def critical_near_field_region_names(self) -> set[str]:
        return {
            name for region in self.critical_regions for name in region.mesh_region_names
        }

    def critical_region_coverage(self) -> dict[str, Any]:
        volume_attributes = {volume.attribute for volume in self.volumes}
        surface_attributes = (
            {surface.attribute for surface in self.surfaces}
            | {interface.attribute for interface in self.interfaces}
            | {port.attribute for port in self.lumped_ports}
            | {port.attribute for port in self.wave_ports}
        )
        near_field_names = {region.name for region in self.mesh_regions}
        declared_volume = self.critical_region_attributes
        declared_surface = self.critical_surface_attributes
        declared_near_field = self.critical_near_field_region_names
        mapped_volume = declared_volume & volume_attributes
        mapped_surface = declared_surface & surface_attributes
        mapped_near_field = declared_near_field & near_field_names
        return {
            "declared_volume_regions": len(declared_volume),
            "mapped_volume_regions": len(mapped_volume),
            "mapped_volume_coverage": (
                len(mapped_volume) / len(declared_volume) if declared_volume else 1.0
            ),
            "declared_surface_regions": len(declared_surface),
            "mapped_surface_regions": len(mapped_surface),
            "mapped_surface_coverage": (
                len(mapped_surface) / len(declared_surface) if declared_surface else 1.0
            ),
            "declared_near_field_regions": len(declared_near_field),
            "mapped_near_field_regions": len(mapped_near_field),
            "mapped_near_field_coverage": (
                len(mapped_near_field) / len(declared_near_field)
                if declared_near_field
                else 1.0
            ),
        }

    @staticmethod
    def _unique(what: str, attributes: list[int]) -> None:
        duplicates = sorted({a for a in attributes if attributes.count(a) > 1})
        if duplicates:
            raise FEMModelError(f"{what} attributes must be unique; reused: {duplicates}")

    # -- projections ------------------------------------------------------

    def physical_groups(self) -> dict[int, list[tuple[int, str]]]:
        """Gmsh physical groups by dimension: ``{dim: [(attribute, name), ...]}``.

        The mesher reads this. It never invents a tag, so a mesh and a config
        built from one model cannot disagree about what attribute 3 is.
        """
        return {
            3: [(v.attribute, v.name) for v in self.volumes],
            2: (
                [(s.attribute, s.name) for s in self.surfaces]
                + [(i.attribute, i.name) for i in self.interfaces]
                + [(p.attribute, p.name) for p in self.lumped_ports]
                + [(p.attribute, p.name) for p in self.wave_ports]
            ),
        }

    def _material_of(self, name: str) -> Material:
        return next(material for material in self.materials if material.name == name)

    def energy_regions(self) -> dict[int, str]:
        """``{postprocessing index: volume name}`` for every energy-tracked volume."""
        tracked = [volume for volume in self.volumes if volume.postprocess_energy]
        return {index: volume.name for index, volume in enumerate(tracked, start=1)}

    def _surfaces_of(self, kind: SurfaceKind) -> list[int]:
        return sorted(s.attribute for s in self.surfaces if s.kind == kind)

    def to_palace_eigenmode_config(self, *, mesh_filename: str, output_dir: str) -> dict[str, Any]:
        """Project onto a Palace eigenmode configuration.

        Deterministic: the same model always yields the same dictionary, so the
        configuration hash in the evidence record identifies the model.
        """
        materials = [
            {
                "Attributes": [volume.attribute],
                "Permeability": self._material_of(volume.material).permeability,
                "Permittivity": self._material_of(volume.material).permittivity,
            }
            for volume in self.volumes
        ]
        for volume in self.volumes:
            material = self._material_of(volume.material)
            if material.loss_tangent > 0:
                materials[self.volumes.index(volume)]["LossTan"] = material.loss_tangent

        domains: dict[str, Any] = {"Materials": materials}
        tracked = [volume for volume in self.volumes if volume.postprocess_energy]
        if tracked:
            domains["Postprocessing"] = {
                "Energy": [
                    {"Index": index, "Attributes": [volume.attribute]}
                    for index, volume in enumerate(tracked, start=1)
                ]
            }

        boundaries: dict[str, Any] = {}
        if pec := self._surfaces_of("pec"):
            boundaries["PEC"] = {"Attributes": pec}
        if pmc := self._surfaces_of("pmc_symmetry"):
            boundaries["PMC"] = {"Attributes": pmc}
        if absorbing := self._surfaces_of("absorbing"):
            boundaries["Absorbing"] = {"Attributes": absorbing, "Order": 1}
        impedance = [s for s in self.surfaces if s.kind == "impedance"]
        if impedance:
            boundaries["Impedance"] = [
                {"Attributes": [s.attribute], "Rs": s.resistance_ohm_per_square}
                for s in sorted(impedance, key=lambda s: s.attribute)
            ]
        if self.lumped_ports:
            boundaries["LumpedPort"] = [
                {
                    "Index": port.index,
                    "Attributes": [port.attribute],
                    "R": port.impedance_ohm,
                    "Direction": port.direction,
                }
                for port in sorted(self.lumped_ports, key=lambda p: p.index)
            ]
        if self.wave_ports:
            boundaries["WavePort"] = [
                {"Index": port.index, "Attributes": [port.attribute], "Mode": port.mode_count}
                for port in sorted(self.wave_ports, key=lambda p: p.index)
            ]

        return {
            "Problem": {"Type": "Eigenmode", "Verbose": 2, "Output": output_dir},
            "Model": {"Mesh": mesh_filename, "L0": self.length_unit_m},
            "Domains": domains,
            "Boundaries": boundaries,
            "Solver": {
                "Order": self.eigenmode.element_order,
                "Device": "CPU",
                "Eigenmode": {
                    "N": self.eigenmode.mode_count,
                    "Tol": self.eigenmode.tolerance,
                    "Target": self.eigenmode.target_frequency_ghz,
                    "Save": 0,
                },
                "Linear": {
                    "Type": "Default",
                    "Tol": self.eigenmode.linear_tolerance,
                    "MaxIts": self.eigenmode.linear_max_iterations,
                },
            },
        }

    def refined(self, factor: float) -> FEMModel:
        """The same model at a different mesh density. Geometry is untouched."""
        return self.model_copy(update={"mesh": self.mesh.scaled(factor)})
