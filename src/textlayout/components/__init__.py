"""High-frequency micro-primitives for superconducting circuit layout.

Each component is a :class:`~textlayout.ports.generator.Generator` with a
Pydantic v2 parameter schema in :mod:`textlayout.schemas.dsl`. They are pure
Python (no numpy, no gdsfactory) so geometry is deterministic across hosts.

Use :func:`register_components` to add them to a
:class:`~textlayout.generators.registry.GeneratorRegistry`.
"""

from __future__ import annotations

from textlayout.components.euler_bend import CPWEulerBendGenerator, euler_centerline
from textlayout.components.junction import JosephsonJunctionGenerator, junction_energy_ghz
from textlayout.components.perforation import PerforationGenerator, perforation_holes
from textlayout.generators.registry import GeneratorRegistry

COMPONENT_GENERATORS = (CPWEulerBendGenerator, PerforationGenerator, JosephsonJunctionGenerator)


def register_components(registry: GeneratorRegistry) -> GeneratorRegistry:
    """Register every micro-primitive generator on ``registry`` and return it."""
    for generator_cls in COMPONENT_GENERATORS:
        registry.register(generator_cls())
    return registry


__all__ = [
    "COMPONENT_GENERATORS",
    "CPWEulerBendGenerator",
    "JosephsonJunctionGenerator",
    "PerforationGenerator",
    "euler_centerline",
    "junction_energy_ghz",
    "perforation_holes",
    "register_components",
]
