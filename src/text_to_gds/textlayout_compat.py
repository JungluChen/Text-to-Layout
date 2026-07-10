"""Backward-compatible bridge: the ``textlayout`` product API under the legacy path.

**Deprecated.** Import from ``textlayout`` directly. This shim exists so legacy
``text_to_gds`` code and downstream users have one tested on-ramp to the
supported namespace while the frozen MCP surface is retired module by module.

It is also the worked example of the consolidation mechanism: a thin re-export
built with :func:`text_to_gds._deprecation.deprecated_reexport`, recognised as a
shim (not new legacy implementation) by ``scripts/check_namespace_boundary.py``.
"""

from __future__ import annotations

from text_to_gds._deprecation import deprecated_reexport

__all__ = deprecated_reexport(
    globals(),
    "textlayout",
    names=[
        "DSL_VERSION",
        "FromTextWorkflow",
        "GenerateWorkflow",
        "GeometryEngine",
        "LayoutSpec",
        "TechnologyLibrary",
        "VerificationReport",
        "build_default_workflow",
        "build_from_text_workflow",
    ],
    since="0.3.0",
    replacement="textlayout",
    removal="1.0.0",
)
