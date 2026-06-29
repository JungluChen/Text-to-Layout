"""The Geometry Engine: ``LayoutSpec`` (DSL) → :class:`Geometry`.

This is the deterministic heart of the system and the *only* place that turns a
DSL request into geometry. It performs no AI, no I/O, and no export. Its three
responsibilities are:

1. resolve the generator for ``spec.component`` (via the injected registry),
2. resolve the technology for ``spec.technology`` (via the injected library),
3. validate ``spec.parameters`` against the generator's typed schema, then build.

Dependencies are injected (registry, technology library) — there is no global
state, so the engine is trivially testable with fakes.
"""

from __future__ import annotations

from pydantic import BaseModel, ValidationError

from textlayout.errors import InvalidParametersError
from textlayout.generators.registry import GeneratorRegistry
from textlayout.knowledge.technology_library import TechnologyLibrary
from textlayout.models import Geometry, Technology
from textlayout.schemas.dsl import LayoutSpec


class BuildResult:
    """The geometry plus the resolved, typed params and technology.

    Returned together because validators need the typed params and the technology,
    not just the geometry — re-deriving them would duplicate the engine's work.
    """

    __slots__ = ("geometry", "params", "technology")

    def __init__(self, geometry: Geometry, params: BaseModel, technology: Technology) -> None:
        self.geometry = geometry
        self.params = params
        self.technology = technology


class GeometryEngine:
    """Converts a validated DSL spec into deterministic geometry."""

    def __init__(self, registry: GeneratorRegistry, technologies: TechnologyLibrary) -> None:
        self._registry = registry
        self._technologies = technologies

    def build(self, spec: LayoutSpec) -> BuildResult:
        generator = self._registry.get(spec.component)  # raises UnknownComponentError
        technology = self._technologies.get(spec.technology)  # raises UnknownTechnologyError

        try:
            params = generator.params_model.model_validate(spec.parameters)
        except ValidationError as exc:
            raise InvalidParametersError(spec.component, _format_errors(exc)) from exc

        geometry = generator.generate(params, technology, spec.origin)
        return BuildResult(geometry=geometry, params=params, technology=technology)

    @property
    def components(self) -> list[str]:
        return self._registry.names()

    @property
    def technologies(self) -> list[str]:
        return self._technologies.names()


def _format_errors(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "<root>"
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts)
