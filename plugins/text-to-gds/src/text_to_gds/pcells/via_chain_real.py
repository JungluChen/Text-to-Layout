"""Fabrication-real via-chain monitor with Kelvin pads and stage labels.

Wraps the existing via_chain_monitor with four-terminal Kelvin measurement
pads, stage markers, and a DRC-compatible layout suitable for process
characterization.
"""

from __future__ import annotations

import gdsfactory as gf

from text_to_gds.pcells.layer_stack import KEEPOUT
from text_to_gds.pcells.passives import via_chain_monitor
from text_to_gds.process import (
    M2,
    M3,
    MARKER,
    VIA23,
    require_positive,
)


def _rect(cx: float, cy: float, w: float, h: float) -> list[tuple[float, float]]:
    hw, hh = w / 2.0, h / 2.0
    return [(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)]


@gf.cell
def via_chain_real(
    stage_count: int = 100,
    pitch: float = 1.0,
    row_offset: float = 5.0,
    metal_width: float = 0.4,
    via_size: float = 0.4,
    enclosure: float = 0.2,
    kelvin_pad_size: float = 80.0,
    kelvin_pad_spacing: float = 20.0,
    estimated_via_resistance_ohm: float = 0.25,
    keepout_margin: float = 10.0,
) -> gf.Component:
    """Fabrication-real via chain with four-terminal Kelvin measurement pads."""
    require_positive("kelvin_pad_size", kelvin_pad_size)
    require_positive("keepout_margin", keepout_margin)

    chain = via_chain_monitor(
        stage_count=stage_count,
        pitch=pitch,
        row_offset=row_offset,
        metal_width=metal_width,
        via_size=via_size,
        enclosure=enclosure,
        estimated_via_resistance_ohm=estimated_via_resistance_ohm,
    )

    c = gf.Component()
    c.add_ref(chain)

    chain_bbox = chain.bbox_np()
    chain_x_min, chain_y_min = chain_bbox[0]
    chain_x_max, chain_y_max = chain_bbox[1]
    chain_cx = (chain_x_min + chain_x_max) / 2.0
    chain_width = chain_x_max - chain_x_min

    pad_y_top = chain_y_max + kelvin_pad_spacing + kelvin_pad_size / 2.0
    pad_y_bot = chain_y_min - kelvin_pad_spacing - kelvin_pad_size / 2.0

    pad_positions = {
        "I+": (chain_x_min, pad_y_bot),
        "I-": (chain_x_max, pad_y_bot),
        "V+": (chain_x_min, pad_y_top),
        "V-": (chain_x_max, pad_y_top),
    }

    for name, (px, py) in pad_positions.items():
        c.add_polygon(_rect(px, py, kelvin_pad_size, kelvin_pad_size), layer=M3)
        c.add_polygon(_rect(px, py, kelvin_pad_size * 0.3, kelvin_pad_size * 0.3), layer=VIA23)
        c.add_polygon(_rect(px, py, kelvin_pad_size, kelvin_pad_size), layer=M2)
        c.add_port(
            name=name,
            center=(px, py),
            width=kelvin_pad_size,
            orientation=90 if "+" in name else 270,
            layer=M3,
            port_type="electrical",
        )

    connect_y = chain_y_min if pad_y_bot < chain_y_min else chain_y_max
    for px, py in [(chain_x_min, pad_y_bot), (chain_x_max, pad_y_bot)]:
        cy = (py + connect_y) / 2.0
        c.add_polygon(_rect(px, cy, metal_width * 3, abs(py - connect_y) + metal_width), layer=M3)

    for milestone in range(0, stage_count, max(stage_count // 5, 1)):
        mx = milestone * pitch
        c.add_label(f"S{milestone}", position=(mx, row_offset + 3.0), layer=MARKER)

    total_w = chain_width + 2 * kelvin_pad_size + 2 * keepout_margin
    total_h = (pad_y_top + kelvin_pad_size / 2.0) - (pad_y_bot - kelvin_pad_size / 2.0) + 2 * keepout_margin
    c.add_polygon(_rect(chain_cx, (pad_y_top + pad_y_bot) / 2.0, total_w, total_h), layer=KEEPOUT)

    c.info.update(dict(chain.info))
    c.info["device_type"] = "via_chain_real"
    c.info["layout_quality_mode"] = "fabrication_real"
    c.info["visualization_only"] = False
    c.info["kelvin_measurement"] = True
    c.info["kelvin_pads"] = list(pad_positions.keys())
    c.info["has_keepout"] = True
    c.info["has_stage_labels"] = True
    c.info["measurement_method"] = "four_terminal_kelvin"
    c.info["expected_resistance_formula"] = "R = N * R_via + R_sheet * L / W"
    c.info["extraction"] = {
        "total_resistance_ohm": {
            "value": chain.info.get("estimated_total_resistance_ohm", 0),
            "method": "estimated",
            "source": "geometric_estimate",
            "formula": "R = N * R_via + R_sheet * L_metal / W_metal",
            "confidence": 0.60,
            "unit": "ohm",
        },
        "via_resistance_ohm": {
            "value": estimated_via_resistance_ohm,
            "method": "estimated",
            "source": "process_parameter",
            "formula": "R_via (process input)",
            "confidence": 0.50,
            "unit": "ohm",
        },
    }
    c.info["quality_record"] = {
        "status": "fabrication_real",
        "checks": ["kelvin_pads", "via_chain_continuity", "keepout", "stage_labels"],
    }
    return c
