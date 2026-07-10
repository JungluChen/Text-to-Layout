"""textlayout — natural-language-driven IC layout generation.

A clean-architecture framework that turns a typed Layout DSL into validated,
exportable IC geometry. The AI never writes GDS: it emits DSL, and this
deterministic core turns DSL into geometry, runs design-rule validation, and
exports to GDS / SVG / JSON.

This module's :func:`build_default_workflow` is the *composition root* — the one
place that wires concrete adapters to abstract ports via dependency injection.
Everything else receives its collaborators through constructors.
"""

from __future__ import annotations

from textlayout.exporters import default_exporters
from textlayout.generators import GeneratorRegistry, default_registry
from textlayout.geometry import GeometryEngine
from textlayout.knowledge import TechnologyLibrary, default_technology_library
from textlayout.schemas.dsl import DSL_VERSION, LayoutSpec
from textlayout.verification import VerificationReport, default_verifier
from textlayout.workflows import FromTextResult, FromTextWorkflow, GenerateResult, GenerateWorkflow

def _distribution_version() -> str:
    """Single source of truth: the installed distribution's own metadata.

    A hardcoded literal here silently drifts from `[project] version` in
    pyproject.toml -- it had, by a full minor release -- and `textlayout
    --version` then misreports the wheel it came from.
    """
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _version

    try:
        return _version("text-to-gds")
    except PackageNotFoundError:  # pragma: no cover - source tree, not installed
        return "0.0.0+unknown"


__version__ = _distribution_version()

__all__ = [
    "DSL_VERSION",
    "FromTextResult",
    "FromTextWorkflow",
    "GenerateResult",
    "GenerateWorkflow",
    "GeneratorRegistry",
    "GeometryEngine",
    "LayoutSpec",
    "TechnologyLibrary",
    "VerificationReport",
    "__version__",
    "build_default_workflow",
    "build_from_text_workflow",
]


def build_default_workflow(
    *,
    registry: GeneratorRegistry | None = None,
    technologies: TechnologyLibrary | None = None,
) -> GenerateWorkflow:
    """Compose a ready-to-use :class:`GenerateWorkflow` from built-in adapters.

    Optional ``registry``/``technologies`` overrides let callers (and tests)
    inject custom generators or PDKs without touching the wiring.
    """
    registry = registry or default_registry()
    technologies = technologies or default_technology_library()
    engine = GeometryEngine(registry=registry, technologies=technologies)
    return GenerateWorkflow(
        engine=engine,
        verifier=default_verifier(),
        exporters=default_exporters(),
    )


def build_from_text_workflow(
    *,
    registry: GeneratorRegistry | None = None,
    technologies: TechnologyLibrary | None = None,
) -> FromTextWorkflow:
    """Compose the prompt → closed-loop workflow on top of the default core."""
    return FromTextWorkflow(build_default_workflow(registry=registry, technologies=technologies))
