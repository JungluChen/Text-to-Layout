"""KQCircuits integration wrapper for validated superconducting PCells."""

from __future__ import annotations

from typing import Any


class KQCircuitsWrapper:
    """Wrapper for KQCircuits superconducting PCells with availability check."""

    def __init__(self) -> None:
        self._available: bool | None = None
        self._junction_class: type | None = None
        self._resonator_class: type | None = None
        self._transmon_class: type | None = None

    def _check_imports(self) -> None:
        if self._available is not None:
            return
        try:
            from kqcircuits.junctions.junction import Junction
            from kqcircuits.resonators.resonator import Resonator
            from kqcircuits.qubits.transmon import Transmon

            self._junction_class = Junction
            self._resonator_class = Resonator
            self._transmon_class = Transmon
            self._available = True
        except ImportError:
            self._available = False

    def is_available(self) -> bool:
        self._check_imports()
        return self._available  # type: ignore[return-value]

    def get_junction_class(self) -> type | None:
        self._check_imports()
        return self._junction_class

    def get_resonator_class(self) -> type | None:
        self._check_imports()
        return self._resonator_class

    def get_transmon_class(self) -> type | None:
        self._check_imports()
        return self._transmon_class

    def create_junction(self, **kwargs: Any) -> Any:
        self._check_imports()
        if self._junction_class is None:
            raise RuntimeError("KQCircuits not available")
        return self._junction_class(**kwargs)

    def create_resonator(self, **kwargs: Any) -> Any:
        self._check_imports()
        if self._resonator_class is None:
            raise RuntimeError("KQCircuits not available")
        return self._resonator_class(**kwargs)

    def create_transmon(self, **kwargs: Any) -> Any:
        self._check_imports()
        if self._transmon_class is None:
            raise RuntimeError("KQCircuits not available")
        return self._transmon_class(**kwargs)
