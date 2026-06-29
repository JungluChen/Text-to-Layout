"""Exporter port — the contract for turning :class:`Geometry` into an artifact.

Every output format (GDS, SVG, JSON, KLayout, …) is an interchangeable
implementation of this interface. The workflow depends only on the abstraction,
so adding a format never touches existing code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from textlayout.models import Geometry, Technology


class Exporter(ABC):
    """Abstract base for a geometry exporter."""

    #: Short format identifier, e.g. ``"svg"``, ``"json"``, ``"gds"``.
    format: ClassVar[str]
    #: File extension *without* the leading dot.
    extension: ClassVar[str]
    #: True for binary formats (e.g. GDSII); False for text formats.
    binary: ClassVar[bool] = False

    @abstractmethod
    def render(self, geometry: Geometry, tech: Technology) -> str:
        """Render ``geometry`` to a text representation.

        Binary exporters should set ``binary = True`` and override
        :meth:`render_bytes` instead; their :meth:`render` may raise.
        """
        raise NotImplementedError

    def render_bytes(self, geometry: Geometry, tech: Technology) -> bytes:
        """Render to bytes. Default encodes :meth:`render` as UTF-8."""
        return self.render(geometry, tech).encode("utf-8")

    def write(self, geometry: Geometry, tech: Technology, path: str | Path) -> Path:
        """Render and write to ``path``; returns the written path."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if self.binary:
            out.write_bytes(self.render_bytes(geometry, tech))
        else:
            out.write_text(self.render(geometry, tech), encoding="utf-8")
        return out
