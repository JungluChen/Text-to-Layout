"""Immutable identity capture for the pinned Gmsh Python runtime."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

EXPECTED_GMSH_VERSION = "4.15.2"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def gmsh_identity() -> dict[str, Any]:
    """Return availability, exact version, module path, and module hash."""
    try:
        import gmsh  # type: ignore[import-untyped]
    except ImportError:
        return {
            "available": False,
            "version": None,
            "expected_version": EXPECTED_GMSH_VERSION,
        }
    version = str(getattr(gmsh, "__version__", "unknown"))
    module = Path(gmsh.__file__).resolve()
    return {
        "available": version == EXPECTED_GMSH_VERSION,
        "version": version,
        "expected_version": EXPECTED_GMSH_VERSION,
        "module": str(module),
        "module_sha256": _sha256(module),
    }
