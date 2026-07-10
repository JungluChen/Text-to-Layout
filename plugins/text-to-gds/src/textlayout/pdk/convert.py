"""Project a rich :class:`PDK` down to the geometry engine's :class:`Technology`.

This is the compatibility bridge: every existing generator, verification
check, and exporter only knows about :class:`textlayout.models.Technology`
(the minimal layer/rule stack). Rather than touch that pipeline, a PDK is
converted once into a ``Technology`` with the same ``name`` as the PDK, so
registering it in the technology library makes it usable via the existing
``LayoutSpec.technology`` field — no CLI or API changes required.
"""

from __future__ import annotations

from textlayout.models import LayerInfo, Technology
from textlayout.pdk.models import PDK


def pdk_to_technology(pdk: PDK) -> Technology:
    """Build the geometry-engine ``Technology`` view of a foundry ``PDK``."""
    layers = {
        layer.name: LayerInfo(
            name=layer.name,
            gds_layer=layer.gds_layer,
            gds_datatype=layer.gds_datatype,
            description=f"{layer.purpose} ({pdk.name})",
            color=layer.color,
        )
        for layer in pdk.layers
    }
    return Technology(
        name=pdk.name,
        layers=layers,
        grid_nm=pdk.grid.grid_nm,
        default_min_spacing_um=pdk.grid.default_min_spacing_um,
        min_spacing_um={layer.name: layer.min_spacing_um for layer in pdk.layers},
        default_min_width_um=pdk.grid.default_min_width_um,
        min_width_um={layer.name: layer.min_width_um for layer in pdk.layers},
        substrate_epsilon_r=pdk.substrate.epsilon_r,
    )
