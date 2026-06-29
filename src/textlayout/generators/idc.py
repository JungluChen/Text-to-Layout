"""Interdigital Capacitor (IDC) generator.

Produces a deterministic, design-rule-respecting interdigital capacitor as the
Geometry IR. Two combs (bottom + top bus) interleave their fingers; opposing
fingers run parallel over ``overlap_um`` separated laterally by ``gap_um`` — the
overlap region sets the capacitance.

Cross-section along x (B = bottom comb finger, T = top comb finger)::

    B   T   B   T   B   T          <- fingers, pitch = finger_width + gap
    ███████████████████████  top bus
    ███████████████████████  bottom bus
"""

from __future__ import annotations

from pydantic import BaseModel

from textlayout.models import Geometry, Point, Polygon, Port, Technology, rectangle
from textlayout.ports.generator import Generator
from textlayout.schemas.dsl.idc import IDCSpec


class IDCGenerator(Generator):
    """Generates an interdigital capacitor."""

    name = "IDC"
    params_model = IDCSpec

    def generate(self, params: BaseModel, tech: Technology, origin: Point) -> Geometry:
        assert isinstance(params, IDCSpec)
        x0, y0 = origin
        n = params.finger_pairs
        fw = params.finger_width_um
        gap = params.gap_um
        overlap = params.overlap_um
        bus = params.bus_width_um
        layer = params.metal_layer

        end_gap = gap  # tip-to-opposite-bus clearance uses the same rule
        finger_len = overlap + end_gap
        pitch = fw + gap
        total_fingers = 2 * n
        width = total_fingers * fw + (total_fingers - 1) * gap

        # Vertical band layout (relative to origin).
        bot_bus_lo = y0
        bot_bus_hi = y0 + bus
        bot_finger_hi = bot_bus_hi + finger_len
        top_bus_lo = bot_bus_hi + finger_len + end_gap
        top_bus_hi = top_bus_lo + bus
        top_finger_lo = bot_bus_hi + end_gap

        polygons: list[Polygon] = [
            rectangle(layer, x0, bot_bus_lo, x0 + width, bot_bus_hi),  # bottom bus
            rectangle(layer, x0, top_bus_lo, x0 + width, top_bus_hi),  # top bus
        ]

        for i in range(total_fingers):
            fx0 = x0 + i * pitch
            fx1 = fx0 + fw
            if i % 2 == 0:  # bottom comb finger (extends up)
                polygons.append(rectangle(layer, fx0, bot_bus_hi, fx1, bot_finger_hi))
            else:  # top comb finger (extends down)
                polygons.append(rectangle(layer, fx0, top_finger_lo, fx1, top_bus_lo))

        cx = x0 + width / 2.0
        ports = (
            Port(name="P1", center=(cx, bot_bus_lo), width=width, orientation=270.0, layer=layer),
            Port(name="P2", center=(cx, top_bus_hi), width=width, orientation=90.0, layer=layer),
        )

        return Geometry(
            name="IDC",
            polygons=tuple(polygons),
            ports=ports,
            metadata={
                "component": "IDC",
                "metal_layer": layer,
                "finger_pairs": n,
                "finger_width_um": fw,
                "gap_um": gap,
                "overlap_um": overlap,
                "bus_width_um": bus,
                "total_width_um": round(width, 4),
                "total_height_um": round(top_bus_hi - bot_bus_lo, 4),
                "min_ports": 2,
                "estimated_capacitance_fF": _estimate_capacitance_ff(n, overlap, fw, gap),
                "capacitance_method": "coarse_analytical_estimate",
                "capacitance_confidence": "low",
            },
        )


def _estimate_capacitance_ff(
    finger_pairs: int, overlap_um: float, finger_width_um: float, gap_um: float
) -> float:
    """Very coarse first-order IDC capacitance estimate (fF).

    Uses a simplified coplanar interdigital model (per-unit-length ~0.5 fF/µm of
    overlapped finger edge for typical thin-film on dielectric). This is a design
    starting point ONLY — it is explicitly labelled low-confidence and must be
    replaced by an EM-extracted value before any performance claim.
    """
    edges = max(2 * finger_pairs - 1, 1)
    c_per_um = 0.5  # fF per µm of overlapped edge (order-of-magnitude placeholder)
    return round(edges * overlap_um * c_per_um / 10.0, 3)
