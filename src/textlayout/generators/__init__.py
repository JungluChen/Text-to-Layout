"""Device generators (plugins) and the registry that discovers them."""

from __future__ import annotations

from textlayout.generators.cpw import CPWGenerator
from textlayout.generators.idc import IDCGenerator
from textlayout.generators.resonator import QuarterWaveResonatorGenerator
from textlayout.generators.registry import (
    ENTRY_POINT_GROUP,
    GeneratorRegistry,
    default_registry,
)
from textlayout.generators.spiral import SpiralInductorGenerator
from textlayout.generators.squid import SQUIDGenerator

__all__ = [
    "ENTRY_POINT_GROUP",
    "CPWGenerator",
    "GeneratorRegistry",
    "IDCGenerator",
    "QuarterWaveResonatorGenerator",
    "SQUIDGenerator",
    "SpiralInductorGenerator",
    "default_registry",
]
