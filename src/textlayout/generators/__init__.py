"""Device generators (plugins) and the registry that discovers them."""

from __future__ import annotations

from textlayout.generators.cpw import CPWGenerator
from textlayout.generators.idc import IDCGenerator
from textlayout.generators.registry import (
    ENTRY_POINT_GROUP,
    GeneratorRegistry,
    default_registry,
)

__all__ = [
    "ENTRY_POINT_GROUP",
    "CPWGenerator",
    "GeneratorRegistry",
    "IDCGenerator",
    "default_registry",
]
