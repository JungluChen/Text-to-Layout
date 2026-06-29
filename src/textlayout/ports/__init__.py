"""Abstract ports (interfaces). DI wires concrete adapters to these seams."""

from __future__ import annotations

from textlayout.ports.exporter import Exporter
from textlayout.ports.generator import Generator

__all__ = [
    "Exporter",
    "Generator",
]
