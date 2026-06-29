"""Generator port — the contract every device generator must satisfy.

A generator turns a *typed* parameter object into deterministic :class:`Geometry`.
It declares the pydantic schema it accepts (``params_model``) so the engine can
validate the DSL's opaque ``parameters`` mapping before calling it.

Open/Closed: new devices are added by implementing this interface and registering
the implementation — never by editing the engine, the registry, or the DSL.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

from textlayout.models import Geometry, Point, Technology


class Generator(ABC):
    """Abstract base for a single-device geometry generator."""

    #: Unique component name, matched against ``LayoutSpec.component``.
    name: str
    #: Pydantic model used to validate and coerce the DSL ``parameters``.
    params_model: type[BaseModel]

    @abstractmethod
    def generate(self, params: BaseModel, tech: Technology, origin: Point) -> Geometry:
        """Build geometry from validated ``params`` placed at ``origin``.

        Implementations must be **pure and deterministic**: identical inputs must
        always yield identical geometry (this is what makes golden tests possible).
        """
        raise NotImplementedError
