"""The Layout DSL envelope — the firewall between AI and geometry.

The agent layer's *only* job is to emit a valid :class:`LayoutSpec`. Everything
below this object is deterministic and AI-free. The envelope is intentionally
generic: it carries a ``component`` name and an opaque ``parameters`` mapping.
Each generator owns a typed parameter schema (e.g. ``CPWSpec``) and validates
``parameters`` against it. This is what makes the system *open for extension*
(add a generator + its schema) and *closed for modification* (the envelope never
changes when a device is added).
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

DSL_VERSION = "1.0"


class LayoutSpec(BaseModel):
    """A single, self-describing layout request.

    Example::

        {
            "dsl_version": "1.0",
            "component": "CPW",
            "technology": "generic_2metal",
            "parameters": {"center_width_um": 10, "gap_um": 6, "length_um": 1000},
            "origin": [0, 0]
        }
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    dsl_version: str = Field(
        default=DSL_VERSION,
        description="DSL schema version; allows backward-compatible evolution.",
    )
    component: str = Field(
        description="Registered generator name, e.g. 'CPW', 'IDC', 'SpiralInductor'.",
    )
    technology: str = Field(
        default="generic_2metal",
        description="Technology/PDK name resolved by the technology library.",
    )
    target: dict[str, float] = Field(
        default_factory=dict,
        description="Design target(s) the layout aims to hit, e.g. "
        "{'capacitance_pf': 0.6, 'frequency_ghz': 6.0}. Used by the research and "
        "report steps to compare the analytical estimate against intent.",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Device parameters; validated against the generator's schema.",
    )
    rules: dict[str, float] = Field(
        default_factory=dict,
        description="Design-rule overrides, e.g. {'min_width_um': 2, 'min_gap_um': 2}. "
        "When omitted, the technology's defaults apply.",
    )
    outputs: dict[str, bool] = Field(
        default_factory=lambda: {"gds": True, "svg": True, "json": True},
        description="Which artifacts to produce.",
    )
    origin: tuple[float, float] = Field(
        default=(0.0, 0.0),
        description="Placement origin in micrometres.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form provenance (intent, requesting agent, etc.).",
    )

    #: Output keys that correspond to real geometry exporters.
    GEOMETRY_FORMATS: ClassVar[tuple[str, ...]] = ("gds", "svg", "json", "png")

    def requested_formats(self) -> list[str]:
        """Return enabled *geometry* export formats (stable order).

        Non-geometry output flags such as ``report`` are intentionally ignored
        here — they are handled by the report/benchmark steps, not the exporters.
        """
        enabled = {fmt for fmt, on in self.outputs.items() if on}
        return [f for f in self.GEOMETRY_FORMATS if f in enabled]
