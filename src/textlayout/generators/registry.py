"""Generator registry with entry-point discovery.

Devices register two ways, in priority order:

1. **Built-ins** — imported explicitly by :func:`default_registry` so the system
   always works in a source checkout (no install step needed for tests).
2. **Entry points** — third-party packages expose generators under the
   ``textlayout.generators`` entry-point group; they are discovered at runtime.
   This is the Open/Closed extension mechanism: ``pip install your-generator`` and
   it appears, with zero changes to this repository.

The registry holds no global mutable singleton; callers build an instance and
inject it.
"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points

from textlayout.errors import UnknownComponentError
from textlayout.ports.generator import Generator

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "textlayout.generators"


class GeneratorRegistry:
    """An injectable map of component name → :class:`Generator` instance."""

    def __init__(self) -> None:
        self._by_name: dict[str, Generator] = {}

    def register(self, generator: Generator) -> None:
        if generator.name in self._by_name:
            logger.debug("Overriding already-registered generator %r", generator.name)
        self._by_name[generator.name] = generator

    def get(self, name: str) -> Generator:
        try:
            return self._by_name[name]
        except KeyError:
            raise UnknownComponentError(name, list(self._by_name)) from None

    def names(self) -> list[str]:
        return sorted(self._by_name)

    def __contains__(self, name: object) -> bool:
        return name in self._by_name

    def load_entry_points(self) -> None:
        """Discover and register generators advertised via entry points."""
        try:
            eps = entry_points(group=ENTRY_POINT_GROUP)
        except TypeError:  # pragma: no cover - very old importlib.metadata
            eps = entry_points().get(ENTRY_POINT_GROUP, [])  # type: ignore[attr-defined]
        for ep in eps:
            try:
                cls = ep.load()
                self.register(cls())
            except Exception:  # pragma: no cover - defensive: a bad plugin must not crash us
                logger.exception("Failed to load generator entry point %r", ep.name)


def default_registry(*, discover: bool = True) -> GeneratorRegistry:
    """Build a registry with built-in generators and (optionally) plugins."""
    from textlayout.generators.cpw import CPWGenerator
    from textlayout.generators.idc import IDCGenerator
    from textlayout.generators.resonator import QuarterWaveResonatorGenerator
    from textlayout.generators.spiral import SpiralInductorGenerator
    from textlayout.generators.squid import SQUIDGenerator

    registry = GeneratorRegistry()
    registry.register(IDCGenerator())
    registry.register(CPWGenerator())
    registry.register(SpiralInductorGenerator())
    registry.register(QuarterWaveResonatorGenerator())
    registry.register(SQUIDGenerator())
    if discover:
        registry.load_entry_points()
    return registry
