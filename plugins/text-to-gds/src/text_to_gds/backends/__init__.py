from __future__ import annotations

from text_to_gds.backends.base import (
    Backend,
    BackendAvailability,
    BackendStatus,
    validate_value_records,
    value_record,
)
from text_to_gds.backends.elmer_backend import ElmerBackend
from text_to_gds.backends.gdsfactory_backend import GDSFactoryBackend
from text_to_gds.backends.josephsoncircuits_backend import JosephsonCircuitsBackend
from text_to_gds.backends.kqcircuits_backend import KQCircuitsBackend
from text_to_gds.backends.openems_backend import OpenEMSBackend
from text_to_gds.backends.palace_backend import PalaceBackend
from text_to_gds.backends.pyepr_backend import PyEPRBackend
from text_to_gds.backends.qiskit_metal_backend import QiskitMetalBackend
from text_to_gds.backends.scqubits_backend import ScqubitsBackend

BACKEND_CLASSES: dict[str, type[Backend]] = {
    "kqcircuits": KQCircuitsBackend,
    "qiskit_metal": QiskitMetalBackend,
    "gdsfactory": GDSFactoryBackend,
    "scqubits": ScqubitsBackend,
    "josephsoncircuits": JosephsonCircuitsBackend,
    "openems": OpenEMSBackend,
    "palace": PalaceBackend,
    "elmer": ElmerBackend,
    "pyepr": PyEPRBackend,
}


def get_backend(name: str) -> Backend:
    try:
        return BACKEND_CLASSES[name]()
    except KeyError as exc:
        raise ValueError(f"Unknown backend {name!r}. Available: {sorted(BACKEND_CLASSES)}") from exc


def list_backends() -> list[dict[str, object]]:
    rows = []
    for name, backend_cls in BACKEND_CLASSES.items():
        backend = backend_cls()
        rows.append(
            {
                "name": name,
                "role": backend.role,
                "source_url": backend.source_url,
                "availability": backend.available().to_dict(),
            }
        )
    return rows


__all__ = [
    "BACKEND_CLASSES",
    "Backend",
    "BackendAvailability",
    "BackendStatus",
    "ElmerBackend",
    "GDSFactoryBackend",
    "JosephsonCircuitsBackend",
    "KQCircuitsBackend",
    "OpenEMSBackend",
    "PalaceBackend",
    "PyEPRBackend",
    "QiskitMetalBackend",
    "ScqubitsBackend",
    "get_backend",
    "list_backends",
    "validate_value_records",
    "value_record",
]
