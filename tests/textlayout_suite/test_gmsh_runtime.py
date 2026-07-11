from __future__ import annotations

from textlayout.mesh.runtime import EXPECTED_GMSH_VERSION, gmsh_identity


def test_pinned_gmsh_runtime_is_identified() -> None:
    identity = gmsh_identity()
    if identity["version"] is None:
        assert identity["available"] is False
        return
    assert identity["available"] is True
    assert identity["version"] == EXPECTED_GMSH_VERSION == "4.15.2"
    assert len(identity["module_sha256"]) == 64
