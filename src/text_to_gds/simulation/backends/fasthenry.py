from __future__ import annotations

from text_to_gds.simulation.backends.base import BackendLifecycle


class FastHenryBackend(BackendLifecycle):
    name = "fasthenry"
