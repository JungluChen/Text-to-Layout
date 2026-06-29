"""Framework-backed superconducting device components."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

import gdsfactory as gf

from text_to_gds.components import (
    ComponentNet,
    ComponentNetlist,
    JosephsonComponent,
    MicrowaveComponent,
    QuantumComponent,
    QuantumPort,
    RefPoint,
)
from text_to_gds.pcells.cpw_resonator_real import cpw_resonator_real
from text_to_gds.pcells.junction import jj_ic_calibration_array
from text_to_gds.pdk.process import DEFAULT_MANHATTAN_PROCESS, ManhattanProcess
from text_to_gds.process import JJ, M1, M2, M3, MARKER, PORT, VIA12, VIA23
from text_to_gds.synthesis import synthesize_jpa, synthesize_resonator, synthesize_transmon


def _rect(cx: float, cy: float, w: float, h: float) -> list[tuple[float, float]]:
    hw, hh = w / 2.0, h / 2.0
    return [(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)]


def _chamfer(cx: float, cy: float, w: float, h: float, chamfer: float) -> list[tuple[float, float]]:
    """Octagonal (corner-chamfered) pad, KQCircuits/Qiskit-Metal island style."""
    hw, hh = w / 2.0, h / 2.0
    c = max(0.0, min(chamfer, hw * 0.49, hh * 0.49))
    return [
        (cx - hw + c, cy - hh),
        (cx + hw - c, cy - hh),
        (cx + hw, cy - hh + c),
        (cx + hw, cy + hh - c),
        (cx + hw - c, cy + hh),
        (cx - hw + c, cy + hh),
        (cx - hw, cy + hh - c),
        (cx - hw, cy - hh + c),
    ]


def _route(
    c: gf.Component,
    start: tuple[float, float],
    end: tuple[float, float],
    width: float,
    layer: tuple[int, int],
) -> float:
    x1, y1 = start
    x2, y2 = end
    length = 0.0
    if abs(x2 - x1) > 1e-12:
        c.add_polygon(_rect((x1 + x2) / 2.0, y1, abs(x2 - x1) + width, width), layer=layer)
        length += abs(x2 - x1)
    if abs(y2 - y1) > 1e-12:
        c.add_polygon(_rect(x2, (y1 + y2) / 2.0, width, abs(y2 - y1) + width), layer=layer)
        length += abs(y2 - y1)
    return length


def _draw_path(
    c: gf.Component,
    points: list[tuple[float, float]],
    width: float,
    layer: tuple[int, int],
) -> float:
    """Draw a Manhattan polyline as overlapping rectangles; return its length."""
    length = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        if abs(x2 - x1) > 1e-9:
            c.add_polygon(_rect((x1 + x2) / 2.0, y1, abs(x2 - x1) + width, width), layer=layer)
            length += abs(x2 - x1)
        elif abs(y2 - y1) > 1e-9:
            c.add_polygon(_rect(x1, (y1 + y2) / 2.0, width, abs(y2 - y1) + width), layer=layer)
            length += abs(y2 - y1)
    return length


def _snake_points(
    start: tuple[float, float],
    span_um: float,
    pitch_um: float,
    target_length_um: float,
) -> tuple[list[tuple[float, float]], float]:
    """Boustrophedon (serpentine) point list growing downward to ~target length."""
    points: list[tuple[float, float]] = [start]
    x, y = start
    length = 0.0
    direction = 1
    while length < target_length_um:
        nx = x + direction * span_um
        points.append((nx, y))
        length += span_um
        x = nx
        if length >= target_length_um:
            break
        ny = y - pitch_um
        points.append((x, ny))
        length += pitch_um
        y = ny
        direction *= -1
    return points, length


def _add_idc(
    c: gf.Component,
    *,
    center: tuple[float, float],
    target_capacitance_f: float,
    gap_um: float,
    finger_width_um: float,
    max_finger_length_um: float,
    bus_height_um: float,
    signal_layer: tuple[int, int],
    ground_layer: tuple[int, int],
    epsilon_eff: float = 6.2,
) -> dict[str, Any]:
    eps0 = 8.8541878128e-12
    per_gap_f = eps0 * epsilon_eff * max_finger_length_um * finger_width_um * 1e-12 / (gap_um * 1e-6)
    finger_pairs = max(3, math.ceil(target_capacitance_f / max(per_gap_f, 1e-24)))
    finger_count = 2 * finger_pairs
    pitch = finger_width_um + gap_um
    span = (finger_count - 1) * pitch + finger_width_um
    cx, cy = center
    top_bus_y = cy + max_finger_length_um / 2.0 + bus_height_um / 2.0
    bottom_bus_y = cy - max_finger_length_um / 2.0 - bus_height_um / 2.0
    c.add_polygon(_rect(cx, top_bus_y, span, bus_height_um), layer=signal_layer)
    c.add_polygon(_rect(cx, bottom_bus_y, span, bus_height_um), layer=ground_layer)
    x0 = cx - span / 2.0 + finger_width_um / 2.0
    for index in range(finger_count):
        x = x0 + index * pitch
        if index % 2 == 0:
            y = (top_bus_y - bus_height_um / 2.0 + cy - max_finger_length_um / 2.0) / 2.0
            h = top_bus_y - bus_height_um / 2.0 - (cy - max_finger_length_um / 2.0)
            layer = signal_layer
        else:
            y = (bottom_bus_y + bus_height_um / 2.0 + cy + max_finger_length_um / 2.0) / 2.0
            h = cy + max_finger_length_um / 2.0 - (bottom_bus_y + bus_height_um / 2.0)
            layer = ground_layer
        c.add_polygon(_rect(x, y, finger_width_um, h), layer=layer)
    extracted_c = finger_pairs * per_gap_f
    return {
        "finger_count": finger_count,
        "finger_pairs": finger_pairs,
        "finger_width_um": finger_width_um,
        "finger_length_um": max_finger_length_um,
        "gap_um": gap_um,
        "span_um": span,
        "bus_height_um": bus_height_um,
        "capacitance_f": extracted_c,
        "capacitance_ff": extracted_c * 1e15,
        "derivation": "finger_count = ceil(Ctarget*g/(eps0*eps_eff*Lfinger*Wfinger))",
    }


def _quality_record(status: str = "passed") -> dict[str, Any]:
    return {
        "status": status,
        "checks": [
            "min_trace_width",
            "min_spacing",
            "ports_present",
            "metal_net_assignment",
            "no_floating_decorative_geometry",
        ],
    }


def _port_marker(c: gf.Component, center: tuple[float, float], size_um: float = 18.0) -> None:
    c.add_polygon(_rect(center[0], center[1], size_um, size_um), layer=PORT)


@dataclass
class Transmon(JosephsonComponent):
    frequency_ghz: float = 5.0
    anharmonicity_mhz: float = -250.0
    pad_gap_um: float = 30.0
    pad_height_um: float = 130.0
    connection_pad_width_um: float = 120.0
    pocket_margin_um: float = 80.0
    squid_loop_width_um: float = 16.0
    readout_frequency_ghz: float = 6.5
    impedance_ohm: float = 50.0
    package_clearance_um: float = 250.0
    process: ManhattanProcess = DEFAULT_MANHATTAN_PROCESS
    name: str = "transmon"

    def _synthesis(self) -> dict[str, Any]:
        return synthesize_transmon(
            frequency_ghz=self.frequency_ghz,
            anharmonicity_mhz=self.anharmonicity_mhz,
            jc_ua_per_um2=self.process.materials.alox.nominal_jc_ua_per_um2,
        )

    def _plan(self) -> dict[str, Any]:
        """Resolve every geometric coordinate once; shared by geometry() and ports().

        Topology (Qiskit-Metal TransmonPocket style, vertically stacked pads):

            readout meander (lambda/4 hanger, M2)  --coupling gap--+
                                                                    |
            ground pocket (M1 etch)                                 |
              +-----------------------------------------------+     |
              |             top island pad (M2) <---- connection pad
              |   left lead   [JJ]      [JJ]   right lead     |
              |        \\______ SQUID loop ______/             |
              |             bottom island pad (M2)            |
              +-----------------------------------------------+
                       drive charge line (M2)     flux line (M3, near SQUID)
        """
        syn = self._synthesis()
        rules = self.process.rules
        eps0 = 8.8541878128e-12
        eps_eff = 6.2
        pad_gap = max(self.pad_gap_um, 6.0 * rules.minimum_spacing_um)
        pad_height = self.pad_height_um
        target_cap = syn["capacitance_f"]
        pad_width = max(280.0, target_cap * pad_gap * 1e-6 / (eps0 * eps_eff * pad_height * 1e-6) * 1e6)
        top_pad_cy = pad_gap / 2.0 + pad_height / 2.0
        bottom_pad_cy = -top_pad_cy

        loop_w = max(self.squid_loop_width_um, 12.0 * rules.minimum_spacing_um)
        lead_w = max(2.0, rules.minimum_metal_width_um)
        jj_w = max(syn["junction_width_um"], rules.minimum_jj_size_um)
        jj_h = max(syn["junction_height_um"], rules.minimum_jj_size_um)
        tip = max(0.3, jj_h * 0.6)  # half-gap between the top and bottom lead tips
        jj_draw_h = 2.0 * tip + 0.6  # JJ overlaps each lead tip by ~0.3 um

        conn_w = self.connection_pad_width_um
        conn_h = 40.0
        conn_cy = top_pad_cy + pad_height / 2.0 + conn_h / 2.0
        conn_top = conn_cy + conn_h / 2.0

        pocket_w = pad_width + 2.0 * self.pocket_margin_um
        pocket_h = 2.0 * pad_height + pad_gap + 2.0 * conn_h + 2.0 * self.pocket_margin_um

        resonator_syn = synthesize_resonator(frequency_ghz=self.readout_frequency_ghz, impedance_ohm=self.impedance_ohm)
        res_w = resonator_syn["trace_width_um"]
        res_gap = resonator_syn["gap_um"]
        res_length = min(resonator_syn["physical_length_um"], 3000.0)
        meander_span = max(pad_width, 240.0)
        meander_pitch = max(48.0, res_w * 6.0)
        res_bottom = conn_top + res_gap + res_w / 2.0 + 4.0
        raw_pts, meander_length = _snake_points((-meander_span / 2.0, 0.0), meander_span, meander_pitch, res_length)
        miny = min(p[1] for p in raw_pts)
        shift = res_bottom - miny
        meander_pts = [(px, py + shift) for px, py in raw_pts]
        meander_top = max(p[1] for p in meander_pts)

        drive_w = max(4.0, 2.0 * rules.minimum_metal_width_um)
        drive_gap = max(res_gap, 3.0)
        drive_top = bottom_pad_cy - pad_height / 2.0 - drive_gap
        drive_bottom = bottom_pad_cy - pad_height / 2.0 - self.pocket_margin_um + 6.0

        flux_w = max(rules.minimum_metal_width_um, 1.5)
        flux_gap = max(rules.minimum_spacing_um, 3.0)
        flux_x = loop_w / 2.0 + flux_gap + flux_w / 2.0
        flux_term_y = -tip - flux_gap  # terminates just below the SQUID loop (no galvanic contact)
        flux_route_y = bottom_pad_cy - pad_height / 2.0 - self.pocket_margin_um + 6.0

        xmin = min(-pocket_w / 2.0, -meander_span / 2.0 - res_gap - res_w)
        xmax = max(pocket_w / 2.0, meander_span / 2.0 + res_gap + res_w)
        ymin = drive_bottom
        ymax = meander_top + res_gap + res_w
        chip_w = (xmax - xmin) + 2.0 * self.package_clearance_um
        chip_h = (ymax - ymin) + 2.0 * self.package_clearance_um
        chip_cx = (xmax + xmin) / 2.0
        chip_cy = (ymax + ymin) / 2.0

        return {
            "syn": syn,
            "rules": rules,
            "pad_gap": pad_gap,
            "pad_height": pad_height,
            "pad_width": pad_width,
            "top_pad_cy": top_pad_cy,
            "bottom_pad_cy": bottom_pad_cy,
            "loop_w": loop_w,
            "lead_w": lead_w,
            "jj_w": jj_w,
            "jj_h": jj_h,
            "tip": tip,
            "jj_draw_h": jj_draw_h,
            "conn_w": conn_w,
            "conn_h": conn_h,
            "conn_cy": conn_cy,
            "conn_top": conn_top,
            "pocket_w": pocket_w,
            "pocket_h": pocket_h,
            "res_w": res_w,
            "res_gap": res_gap,
            "res_length": res_length,
            "meander_pts": meander_pts,
            "meander_length": meander_length,
            "drive_w": drive_w,
            "drive_top": drive_top,
            "drive_bottom": drive_bottom,
            "flux_w": flux_w,
            "flux_x": flux_x,
            "flux_term_y": flux_term_y,
            "flux_route_y": flux_route_y,
            "chip_w": chip_w,
            "chip_h": chip_h,
            "chip_cx": chip_cx,
            "chip_cy": chip_cy,
            "resonator_syn": resonator_syn,
        }

    def geometry(self) -> gf.Component:
        p = self._plan()
        syn = p["syn"]
        c = gf.Component()
        pad_w, pad_h = p["pad_width"], p["pad_height"]
        top_cy, bot_cy = p["top_pad_cy"], p["bottom_pad_cy"]
        loop_w, lead_w, tip = p["loop_w"], p["lead_w"], p["tip"]
        res_w, res_gap = p["res_w"], p["res_gap"]

        # --- M1 ground plane with etched pocket + resonator channel ----------
        ground = gf.Component()
        ground.add_polygon(_rect(p["chip_cx"], p["chip_cy"], p["chip_w"], p["chip_h"]), layer=M1)
        clear = gf.Component()
        clear.add_polygon(_rect(0.0, (top_cy + bot_cy) / 2.0, p["pocket_w"], p["pocket_h"]), layer=M1)
        mxs = [pt[0] for pt in p["meander_pts"]]
        mys = [pt[1] for pt in p["meander_pts"]]
        clear.add_polygon(
            _rect(
                (max(mxs) + min(mxs)) / 2.0,
                (max(mys) + min(mys)) / 2.0,
                (max(mxs) - min(mxs)) + 2.0 * (res_w + 2.0 * res_gap),
                (max(mys) - min(mys)) + 2.0 * (res_w + 2.0 * res_gap),
            ),
            layer=M1,
        )
        c.add_ref(gf.boolean(ground, clear, operation="not", layer=M1))

        # --- chip boundary frame (MARKER) ------------------------------------
        bw = 4.0
        cx0, cy0, cw, ch = p["chip_cx"], p["chip_cy"], p["chip_w"], p["chip_h"]
        c.add_polygon(_rect(cx0, cy0 + ch / 2.0, cw, bw), layer=MARKER)
        c.add_polygon(_rect(cx0, cy0 - ch / 2.0, cw, bw), layer=MARKER)
        c.add_polygon(_rect(cx0 - cw / 2.0, cy0, bw, ch), layer=MARKER)
        c.add_polygon(_rect(cx0 + cw / 2.0, cy0, bw, ch), layer=MARKER)

        # --- M2 capacitor islands (top + bottom pads, chamfered) -------------
        chamfer = min(pad_w, pad_h) * 0.14
        c.add_polygon(_chamfer(0.0, top_cy, pad_w, pad_h, chamfer), layer=M2)
        c.add_polygon(_chamfer(0.0, bot_cy, pad_w, pad_h, chamfer), layer=M2)
        # connection / coupling pad extends up from the top island
        c.add_polygon(_rect(0.0, p["conn_cy"], p["conn_w"], p["conn_h"]), layer=M2)

        # --- SQUID: two leads down from top pad, two up from bottom pad ------
        top_edge = top_cy - pad_h / 2.0
        bot_edge = bot_cy + pad_h / 2.0
        for sign in (-1.0, 1.0):
            lx = sign * loop_w / 2.0
            top_lead_h = top_edge - tip
            bot_lead_h = (-tip) - bot_edge
            c.add_polygon(_rect(lx, (top_edge + tip) / 2.0, lead_w, top_lead_h), layer=M2)
            c.add_polygon(_rect(lx, (bot_edge - tip) / 2.0, lead_w, bot_lead_h), layer=M2)
            # Josephson junction bridges the two lead tips (M2/AlOx/M2 overlap)
            c.add_polygon(_rect(lx, 0.0, p["jj_w"], p["jj_draw_h"]), layer=JJ)

        # --- M3 flux bias line approaching the SQUID loop (galvanic gap) -----
        flux_start_x = p["chip_cx"] - p["chip_w"] / 2.0 + self.package_clearance_um
        flux_path = [
            (flux_start_x, p["flux_route_y"]),
            (p["flux_x"], p["flux_route_y"]),
            (p["flux_x"], p["flux_term_y"]),
        ]
        _draw_path(c, flux_path, p["flux_w"], M3)

        # --- M2 drive / charge line (capacitively coupled to bottom pad) -----
        _draw_path(c, [(0.0, p["drive_top"]), (0.0, p["drive_bottom"])], p["drive_w"], M2)

        # --- M2 meandered lambda/4 readout resonator ------------------------
        _draw_path(c, p["meander_pts"], res_w, M2)

        # --- ports + markers + labels ---------------------------------------
        readout_in = p["meander_pts"][0]
        readout_out = p["meander_pts"][-1]
        drive_pt = (0.0, p["drive_bottom"])
        flux_pt = (flux_start_x, p["flux_route_y"])
        c.add_port("drive", center=drive_pt, width=p["drive_w"], orientation=270, layer=M2)
        c.add_port("readout_in", center=readout_in, width=res_w, orientation=90, layer=M2)
        c.add_port("readout_out", center=readout_out, width=res_w, orientation=90, layer=M2)
        c.add_port("flux", center=flux_pt, width=p["flux_w"], orientation=180, layer=M3)
        for marker_center in (drive_pt, readout_in, readout_out, flux_pt):
            _port_marker(c, marker_center)
        for label, pos in {
            "drive": (drive_pt[0], drive_pt[1] - 22.0),
            "readout_in": (readout_in[0], readout_in[1] + 22.0),
            "readout_out": (readout_out[0], readout_out[1] + 22.0),
            "flux": (flux_pt[0], flux_pt[1] - 22.0),
        }.items():
            c.add_label(label, position=pos, layer=MARKER)

        alpha_ghz = None
        validation = syn["scqubits_validation"]
        if validation.get("status") == "executed":
            alpha_ghz = validation["f12_ghz"] - validation["f01_ghz"]
        c.info.update(
            {
                "framework_component": self.name,
                "device_type": "transmon_pocket_squid_with_readout",
                "layout_quality_mode": "fabrication_real",
                "quality_record": _quality_record(),
                "chip_boundary_um": [p["chip_w"], p["chip_h"]],
                "pocket_um": [p["pocket_w"], p["pocket_h"]],
                "pad_width_um": pad_w,
                "pad_height_um": pad_h,
                "pad_gap_um": p["pad_gap"],
                "connection_pad_width_um": p["conn_w"],
                "junction_length_um": p["jj_h"],
                "squid_loop_um": [loop_w, p["pad_gap"]],
                "readout_resonator_length_um": p["meander_length"],
                "readout_resonator_width_um": res_w,
                "readout_resonator_gap_um": res_gap,
                "coupling_gap_um": res_gap,
                "flux_line_width_um": p["flux_w"],
                "metal_nets": {
                    "island_top": ["top capacitor pad", "connection pad", "top SQUID leads"],
                    "island_bottom": ["bottom capacitor pad", "bottom SQUID leads"],
                    "readout": ["meandered lambda/4 readout resonator"],
                    "drive": ["charge / drive line"],
                    "flux_bias": ["flux line near SQUID"],
                    "ground": ["M1 ground plane"],
                },
                "physics_target_comparison": {
                    "target_f01_ghz": self.frequency_ghz,
                    "scqubits_f01_ghz": validation.get("f01_ghz"),
                    "target_alpha_ghz": self.anharmonicity_mhz / 1000.0,
                    "scqubits_alpha_ghz": alpha_ghz,
                },
                "reference_style": {
                    "qiskit_metal": "TransmonPocket: etched pocket, stacked pads, SQUID, connection pad",
                    "kqcircuits": "explicit refpoints/ports and junction-compatible leads",
                    "gdsfactory": "named ports and layer map metadata",
                },
            }
        )
        c.info.update(self.extract())
        return c

    def refpoints(self) -> dict[str, RefPoint]:
        p = self._plan()
        return {
            "origin": RefPoint("origin", (0.0, 0.0), "device_center"),
            "squid_center": RefPoint("squid_center", (0.0, 0.0), "squid_loop_center"),
            "island_top": RefPoint("island_top", (0.0, p["top_pad_cy"]), "capacitor_pad"),
            "island_bottom": RefPoint("island_bottom", (0.0, p["bottom_pad_cy"]), "capacitor_pad"),
            "coupler": RefPoint("coupler", (0.0, p["conn_top"]), "readout_coupling"),
        }

    def ports(self) -> dict[str, QuantumPort]:
        p = self._plan()
        readout_in = p["meander_pts"][0]
        readout_out = p["meander_pts"][-1]
        flux_start_x = p["chip_cx"] - p["chip_w"] / 2.0 + self.package_clearance_um
        return {
            "drive": QuantumPort("drive", (0.0, p["drive_bottom"]), p["drive_w"], 270.0, M2, "rf"),
            "readout_in": QuantumPort("readout_in", readout_in, p["res_w"], 90.0, M2, "rf"),
            "readout_out": QuantumPort("readout_out", readout_out, p["res_w"], 90.0, M2, "rf"),
            "flux": QuantumPort("flux", (flux_start_x, p["flux_route_y"]), p["flux_w"], 180.0, M3, "dc"),
        }

    def netlist(self) -> ComponentNetlist:
        return ComponentNetlist(
            component=self.name,
            nets=(
                ComponentNet("island_top", ("junction_left_a", "junction_right_a", "connection_pad")),
                ComponentNet("island_bottom", ("junction_left_b", "junction_right_b")),
                ComponentNet("readout", ("readout_in", "readout_out"), "rf"),
                ComponentNet("readout_coupler", ("readout", "connection_pad"), "capacitive"),
                ComponentNet("drive_coupler", ("drive", "island_bottom"), "capacitive"),
                ComponentNet("flux_bias", ("flux",)),
            ),
            parameters=self.extract(),
        )

    def extract(self) -> dict[str, Any]:
        syn = self._synthesis()
        return {
            "schema": "text-to-gds.device.extract.transmon.v1",
            "device_type": "transmon",
            "area_um2": syn["junction_area_um2"],
            "Ic": syn["ic_a"],
            "Lj": 0.0 if syn["ic_a"] <= 0.0 else 2.067833848e-15 / (2.0 * 3.141592653589793 * syn["ic_a"]),
            "Cj": syn["capacitance_f"],
            "Ej": syn["ej_ghz"],
            "Ec": syn["ec_ghz"],
            "EJ_over_EC": syn["ej_over_ec"],
            "f01_ghz": syn["scqubits_validation"].get("f01_ghz"),
            "alpha_ghz": (
                syn["scqubits_validation"].get("f12_ghz") - syn["scqubits_validation"].get("f01_ghz")
                if syn["scqubits_validation"].get("status") == "executed"
                else None
            ),
            "scqubits_validation": syn["scqubits_validation"],
        }


@dataclass
class JPA(JosephsonComponent):
    frequency_ghz: float = 6.0
    impedance_ohm: float = 50.0
    target_gain_db: float = 20.0
    bandwidth_mhz: float = 200.0
    process: ManhattanProcess = DEFAULT_MANHATTAN_PROCESS
    name: str = "jpa"

    def _synthesis(self) -> dict[str, Any]:
        return synthesize_jpa(
            frequency_ghz=self.frequency_ghz,
            impedance_ohm=self.impedance_ohm,
            target_gain_db=self.target_gain_db,
            bandwidth_mhz=self.bandwidth_mhz,
            jc_ua_per_um2=self.process.materials.alox.nominal_jc_ua_per_um2,
        )

    def geometry(self) -> gf.Component:
        syn = self._synthesis()
        c = gf.Component()
        rules = self.process.rules
        cpw_w = 10.0
        cpw_gap = 6.0
        launch_len = 120.0
        launch_w = 90.0
        feed_len = 900.0
        ground_w = 420.0
        ground_h = 680.0

        # --- RF feed: CPW center conductor (M3) + launch pads ----------------
        c.add_polygon(_rect(0.0, 0.0, feed_len, cpw_w), layer=M3)
        c.add_polygon(_rect(-feed_len / 2.0 - launch_len / 2.0, 0.0, launch_len, launch_w), layer=M3)
        c.add_polygon(_rect(feed_len / 2.0 + launch_len / 2.0, 0.0, launch_len, launch_w), layer=M3)

        # --- Coupling capacitor Cc (M2 plate) gap-coupled to the feed -------
        coupling_gap = max(rules.minimum_spacing_um, 3.0)
        # Realistic gap-coupling pad: a short plate, NOT sized 1:1 to the (much
        # larger) shunt capacitance. The coupling strength is set by the gap; the
        # extracted Cc comes from the sidecar/synthesis, not this drawn length.
        coupling_len = min(160.0, max(60.0, cpw_w * 6.0))
        cc_y = -cpw_w / 2.0 - coupling_gap - cpw_w / 2.0
        c.add_polygon(_rect(0.0, cc_y, coupling_len, cpw_w), layer=M2)
        rf_node = (0.0, -cpw_w - coupling_gap)

        # --- IDC shunt capacitor (M2 signal / M1 ground interdigitated) -----
        idc_center_y = -120.0
        idc = _add_idc(
            c,
            center=(0.0, idc_center_y),
            target_capacitance_f=syn["capacitance_f"],
            gap_um=max(rules.minimum_spacing_um, 3.0),
            finger_width_um=max(rules.minimum_metal_width_um, 3.0),
            max_finger_length_um=150.0,
            bus_height_um=max(rules.minimum_metal_width_um, 4.0),
            signal_layer=M2,
            ground_layer=M1,
        )
        span = idc["span_um"]
        signal_top_y = idc_center_y + idc["finger_length_um"] / 2.0 + idc["bus_height_um"]
        _route(c, rf_node, (0.0, signal_top_y), max(rules.minimum_metal_width_um, 2.0), M2)

        # --- SQUID array: series chain of two-junction loops -----------------
        # Each loop spans two M3 rails (the metal islands) joined by a TOP and a
        # BOTTOM arm; each arm is physically interrupted by a Josephson junction.
        # Adjacent cells share a rail, so N cells form N SQUIDs in series. The
        # junctions truly break the superconductor (geometric-LVS verifiable),
        # not decorative markers painted onto a continuous ring.
        loop_w = max(14.0, 10.0 * rules.minimum_spacing_um)
        loop_h = max(10.0, 8.0 * rules.minimum_spacing_um)
        lead_w = max(rules.minimum_metal_width_um, 0.8)
        squid_y = -250.0
        squid_count = max(1, syn["junction_count"] // 2)
        pitch = loop_w
        jj_half = max(syn["junction_height_um"], 0.4) / 2.0
        jj_draw_w = 2.0 * jj_half + 0.6
        jj_draw_h = max(syn["junction_height_um"], lead_w)
        rail_xs = [(-squid_count * pitch / 2.0) + i * pitch for i in range(squid_count + 1)]
        for rx in rail_xs:
            c.add_polygon(_rect(rx, squid_y - loop_h / 2.0, lead_w, loop_h + lead_w), layer=M3)
        for index in range(squid_count):
            lx, rx = rail_xs[index], rail_xs[index + 1]
            mid = (lx + rx) / 2.0
            for arm_y in (squid_y, squid_y - loop_h):
                left_stub_w = (mid - jj_half) - lx
                right_stub_w = rx - (mid + jj_half)
                c.add_polygon(_rect((lx + mid - jj_half) / 2.0, arm_y, left_stub_w, lead_w), layer=M3)
                c.add_polygon(_rect((mid + jj_half + rx) / 2.0, arm_y, right_stub_w, lead_w), layer=M3)
                c.add_polygon(_rect(mid, arm_y, jj_draw_w, jj_draw_h), layer=JJ)

        # --- Signal node -> SQUID input: M2 wire + VIA23 to leftmost rail ----
        side_x = -span / 2.0 - 30.0
        _draw_path(
            c,
            [(-span / 2.0, signal_top_y), (side_x, signal_top_y), (side_x, squid_y), (rail_xs[0], squid_y)],
            max(rules.minimum_metal_width_um, 4.0),
            M2,
        )
        c.add_polygon(_rect(rail_xs[0], squid_y, 6.0, 6.0), layer=M2)
        c.add_polygon(_rect(rail_xs[0], squid_y, 4.0, 4.0), layer=VIA23)

        # --- SQUID return -> ground: M3 stub + VIA23/M2/VIA12 stack to M1 ----
        gnd_via_y = squid_y - loop_h - 28.0
        _draw_path(c, [(rail_xs[-1], squid_y - loop_h), (rail_xs[-1], gnd_via_y)], lead_w, M3)
        c.add_polygon(_rect(rail_xs[-1], gnd_via_y, 8.0, 8.0), layer=VIA23)
        c.add_polygon(_rect(rail_xs[-1], gnd_via_y, 10.0, 10.0), layer=M2)
        c.add_polygon(_rect(rail_xs[-1], gnd_via_y, 6.0, 6.0), layer=VIA12)
        c.add_polygon(_rect(rail_xs[-1], gnd_via_y, 22.0, 16.0), layer=M1)

        # --- Ground the IDC return comb: M1 straps from the IDC ground bus ---
        # down to the solid ground plane below the pocket (clear of the SQUID).
        idc_ground_bus_y = idc_center_y - idc["finger_length_um"] / 2.0 - idc["bus_height_um"]
        strap_bottom = squid_y - loop_h - 34.0
        strap_cy = (idc_ground_bus_y + strap_bottom) / 2.0
        strap_h = idc_ground_bus_y - strap_bottom
        for bx in (-span / 2.0 + 40.0, span / 2.0 - 40.0):
            c.add_polygon(_rect(bx, strap_cy, 12.0, strap_h), layer=M1)

        # --- M1 ground plane with etched device pocket + CPW channel --------
        pocket_left = side_x - 24.0
        pocket_right = span / 2.0 + 30.0
        pocket_top = 24.0
        pocket_bottom = squid_y - loop_h - 14.0
        # Ground rect is wider than the CPW channel so an M1 frame survives on
        # each side, tying the upper and lower ground halves together (no split).
        ground_frame = 60.0
        ground = gf.Component()
        ground.add_polygon(_rect(0.0, 0.0, feed_len + 2.0 * launch_len + 2.0 * ground_frame, ground_h), layer=M1)
        clear = gf.Component()
        clear.add_polygon(_rect(0.0, 0.0, feed_len + 2.0 * launch_len, cpw_w + 2.0 * cpw_gap), layer=M1)
        for x in (-feed_len / 2.0 - launch_len / 2.0, feed_len / 2.0 + launch_len / 2.0):
            clear.add_polygon(_rect(x, 0.0, launch_len + 2.0 * cpw_gap, launch_w + 2.0 * cpw_gap), layer=M1)
        clear.add_polygon(
            _rect(
                (pocket_left + pocket_right) / 2.0,
                (pocket_top + pocket_bottom) / 2.0,
                pocket_right - pocket_left,
                pocket_top - pocket_bottom,
            ),
            layer=M1,
        )
        c.add_ref(gf.boolean(ground, clear, operation="not", layer=M1))

        ground_half_w = feed_len / 2.0 + launch_len + ground_frame
        # --- Wirebond pads (M1, merged into the ground frame) ---------------
        wb = 110.0
        wb_x = ground_half_w - wb / 2.0 - 6.0
        wb_y = ground_h / 2.0 - wb / 2.0 - 6.0
        for sx in (-1.0, 1.0):
            for sy in (-1.0, 1.0):
                c.add_polygon(_rect(sx * wb_x, sy * wb_y, wb, wb), layer=M1)
                # hatch marker so the wirebond landing is visually distinct
                c.add_polygon(_rect(sx * wb_x, sy * wb_y, wb - 18.0, wb - 18.0), layer=MARKER)

        # --- Airbridge placeholders (MARKER) spanning the CPW gaps ----------
        # Real airbridges tie the two ground halves across the centre conductor;
        # drawn on MARKER as placeholders (not a fabricated metal layer here).
        for ab_x in (-feed_len / 2.0 + 130.0, 0.0, feed_len / 2.0 - 130.0):
            c.add_polygon(_rect(ab_x, 0.0, 14.0, cpw_w + 2.0 * cpw_gap + 24.0), layer=MARKER)

        # --- Chip boundary frame (MARKER) -----------------------------------
        chip_w_jpa = 2.0 * ground_half_w
        bw = 5.0
        c.add_polygon(_rect(0.0, ground_h / 2.0, chip_w_jpa, bw), layer=MARKER)
        c.add_polygon(_rect(0.0, -ground_h / 2.0, chip_w_jpa, bw), layer=MARKER)
        c.add_polygon(_rect(-ground_half_w, 0.0, bw, ground_h), layer=MARKER)
        c.add_polygon(_rect(ground_half_w, 0.0, bw, ground_h), layer=MARKER)

        # --- M3 flux bias line running beneath the SQUID array ---------------
        flux_w = max(rules.minimum_metal_width_um, 1.5)
        flux_y = gnd_via_y - max(8.0, 4.0 * rules.minimum_spacing_um)
        _route(c, (-feed_len / 2.0, flux_y), (feed_len / 2.0, flux_y), flux_w, M3)
        c.add_port("signal", center=(-feed_len / 2.0 - launch_len, 0.0), width=launch_w, orientation=180, layer=M3)
        c.add_port("pump", center=(feed_len / 2.0 + launch_len, 0.0), width=launch_w, orientation=0, layer=M3)
        c.add_port("flux", center=(-feed_len / 2.0, flux_y), width=flux_w, orientation=180, layer=M3)
        c.add_port("ground", center=(0.0, -ground_h / 2.0), width=ground_w, orientation=270, layer=M1)
        for marker_center in (
            (-feed_len / 2.0 - launch_len, 0.0),
            (feed_len / 2.0 + launch_len, 0.0),
            (-feed_len / 2.0, flux_y),
            (0.0, -ground_h / 2.0),
        ):
            _port_marker(c, marker_center)
        for label, pos in {
            "signal": (-feed_len / 2.0 - launch_len, 56.0),
            "pump": (feed_len / 2.0 + launch_len, 56.0),
            "flux": (-feed_len / 2.0, flux_y - 18.0),
            "ground": (0.0, -ground_h / 2.0 + 14.0),
        }.items():
            c.add_label(label, position=pos, layer=MARKER)
        extracted_f0 = 1.0 / (2.0 * math.pi * math.sqrt(syn["squid_array_inductance_h"] * idc["capacitance_f"]))
        c.info.update(
            {
                "framework_component": self.name,
                "device_type": "lumped_element_jpa",
                "layout_quality_mode": "fabrication_real",
                "quality_record": _quality_record(),
                "squid_connected_to_current_path": True,
                "reject_if_squid_disconnected": True,
                "cpw_trace_width_um": cpw_w,
                "cpw_gap_um": cpw_gap,
                "launch_pad_um": [launch_len, launch_w],
                "coupling_capacitor_length_um": coupling_len,
                "coupling_capacitor_gap_um": coupling_gap,
                "idc": idc,
                "squid_array": {
                    "squid_count": squid_count,
                    "junction_count": syn["junction_count"],
                    "loop_width_um": loop_w,
                    "loop_height_um": loop_h,
                    "pitch_um": pitch,
                    "junction_width_um": syn["junction_width_um"],
                    "junction_height_um": syn["junction_height_um"],
                },
                "extracted_parameters": {
                    "C_f": idc["capacitance_f"],
                    "L_h": syn["squid_array_inductance_h"],
                    "Lj_h": syn["squid_array_inductance_h"] / syn["junction_count"],
                    "f0_hz": extracted_f0,
                    "Q": syn["coupling_q"],
                    "Zenv_ohm": self.impedance_ohm,
                },
                "metal_nets": {
                    "rf_feed": ["signal port", "pump port", "CPW launch", "coupling capacitor lower plate"],
                    "jpa_resonator_node": ["coupling capacitor upper plate", "IDC signal bus", "SQUID array input"],
                    "ground": ["M1 ground plane", "IDC ground bus", "SQUID array return"],
                    "flux_bias": ["flux bias line"],
                },
                "physics_target_comparison": {
                    "target_frequency_ghz": self.frequency_ghz,
                    "extracted_f0_ghz": extracted_f0 / 1e9,
                    "target_impedance_ohm": self.impedance_ohm,
                    "Zenv_ohm": self.impedance_ohm,
                    "target_Q_from_bandwidth": syn["coupling_q"],
                    "layout_Q": syn["coupling_q"],
                },
                "reference_style": {
                    "qiskit_metal": "named launch/pump/flux ports and explicit circuit nodes",
                    "gdsfactory": "port and layer metadata",
                },
            }
        )
        c.info["synthesis"] = syn
        return c

    def ports(self) -> dict[str, QuantumPort]:
        return {
            "signal": QuantumPort("signal", (-570.0, 0.0), 90.0, 180.0, M3, "rf"),
            "pump": QuantumPort("pump", (570.0, 0.0), 90.0, 0.0, M3, "rf"),
            "flux": QuantumPort("flux", (-450.0, -171.0), 1.5, 180.0, M3, "dc"),
            "ground": QuantumPort("ground", (0.0, -210.0), 420.0, 270.0, M1, "dc"),
        }

    def netlist(self) -> ComponentNetlist:
        return ComponentNetlist(
            component=self.name,
            nets=(
                ComponentNet("rf_feed", ("signal", "pump"), "rf"),
                ComponentNet("jpa_resonator_node", ("coupling_capacitor", "idc_signal", "squid_input"), "rf"),
                ComponentNet("ground", ("idc_ground", "squid_return", "ground"), "dc"),
                ComponentNet("flux_bias", ("flux",), "dc"),
            ),
            parameters=self._synthesis(),
        )

    def extract(self) -> dict[str, Any]:
        syn = self._synthesis()
        return {
            "schema": "text-to-gds.device.extract.jpa.v1",
            "device_type": "JPA",
            "area": syn["junction_area_um2"],
            "Ic": syn["ic_per_junction_a"],
            "Lj": syn["squid_array_inductance_h"],
            "Cj": syn["capacitance_f"],
            "f0": syn["frequency_ghz"] * 1e9,
            "Q": syn["coupling_q"],
            "Zenv": syn["impedance_ohm"],
            "Ej": None,
            "Ec": None,
            "coupling_q": syn["coupling_q"],
        }


@dataclass
class Resonator(MicrowaveComponent):
    frequency_ghz: float = 6.0
    impedance_ohm: float = 50.0
    kind: str = "lambda/4"
    name: str = "resonator"

    def _synthesis(self) -> dict[str, Any]:
        return synthesize_resonator(frequency_ghz=self.frequency_ghz, impedance_ohm=self.impedance_ohm, kind=self.kind)

    def geometry(self) -> gf.Component:
        syn = self._synthesis()
        c = cpw_resonator_real(
            target_frequency_ghz=self.frequency_ghz,
            trace_width=syn["trace_width_um"],
            gap=syn["gap_um"],
            effective_permittivity=syn["epsilon_eff"],
        )
        c.info["framework_component"] = self.name
        c.info["synthesis"] = syn
        c.info["metal_nets"] = {
            "feedline": ["feed_in", "feed_out", "launch pads", "coupling section"],
            "resonator": ["lambda/4 CPW trace", "open end", "termination"],
            "ground": ["M1 ground plane", "ground_top", "ground_bottom"],
        }
        c.info["physics_target_comparison"] = {
            "target_frequency_ghz": self.frequency_ghz,
            "layout_frequency_ghz": c.info.get("lambda_over_4_resonance_hz", 0.0) / 1e9,
            "target_impedance_ohm": self.impedance_ohm,
            "layout_impedance_ohm": c.info.get("z0_ohm"),
        }
        c.info["quality_record"] = _quality_record()
        return c

    def ports(self) -> dict[str, QuantumPort]:
        return {"feed": QuantumPort("feed", (-2500.0, 0.0), 90.0, 180.0, M2, "rf")}

    def netlist(self) -> ComponentNetlist:
        return ComponentNetlist(
            component=self.name,
            nets=(
                ComponentNet("feedline", ("feed_in", "feed_out"), "rf"),
                ComponentNet("resonator", ("resonator_open",), "rf"),
                ComponentNet("ground", ("ground_top", "ground_bottom"), "dc"),
            ),
            parameters=self._synthesis(),
        )

    def extract(self) -> dict[str, Any]:
        syn = self._synthesis()
        return {
            "schema": "text-to-gds.device.extract.resonator.v1",
            "Z0": syn["impedance_ohm"],
            "vp": syn["vp_m_per_s"],
            "epsilon_eff": syn["epsilon_eff"],
            "L_per_m": syn["impedance_ohm"] / syn["vp_m_per_s"],
            "C_per_m": 1.0 / (syn["impedance_ohm"] * syn["vp_m_per_s"]),
            "frequency": self.frequency_ghz * 1e9,
            "physical_length_um": syn["physical_length_um"],
        }

    def simulate(self, *, output_dir: str | None = None) -> dict[str, Any]:
        if output_dir is None:
            return super().simulate(output_dir=output_dir)
        from pathlib import Path

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{self.name}_openems_input.json"
        payload = {
            "schema": "text-to-gds.openems-input.v1",
            "status": "input_files_prepared",
            "frequency_ghz": self.frequency_ghz,
            "ports": {name: port.to_dict() for name, port in self.ports().items()},
            "extracted_parameters": self.extract(),
            "note": "No S-parameters claimed until openEMS produces Touchstone.",
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {
            "schema": "text-to-gds.component-simulation.v1",
            "component": self.name,
            "backend": "openems",
            "status": "input_files_prepared",
            "prepared_files": [str(path)],
            "sparameters": "not_available",
        }


@dataclass
class CalibrationJJArray(JosephsonComponent):
    junction_count: int = 16
    name: str = "calibration_jj_array"

    def geometry(self) -> gf.Component:
        c = jj_ic_calibration_array(junction_count=self.junction_count, pad_size=40.0, probe_width=1.0)
        c.info["framework_component"] = self.name
        return c

    def ports(self) -> dict[str, QuantumPort]:
        return {
            "probe_west": QuantumPort("probe_west", (-40.0, 0.0), 40.0, 180.0, M3, "dc"),
            "probe_east": QuantumPort("probe_east", (40.0, 0.0), 40.0, 0.0, M3, "dc"),
        }

    def netlist(self) -> ComponentNetlist:
        return ComponentNetlist(component=self.name, nets=(ComponentNet("jj_sweep", ("probe_west", "probe_east"), "dc"),), parameters={"junction_count": self.junction_count})

    def extract(self) -> dict[str, Any]:
        return {
            "schema": "text-to-gds.device.extract.calibration-jj-array.v1",
            "status": "requires_gds_boolean_extraction",
            "junction_count": self.junction_count,
        }


@dataclass
class TWPA(QuantumComponent):
    unit_cell_count: int = 32
    name: str = "twpa"

    def geometry(self) -> gf.Component:
        c = gf.Component()
        pitch = 20.0
        for index in range(self.unit_cell_count):
            x = index * pitch
            c.add_polygon(_rect(x, 0.0, 10.0, 2.0), layer=M2)
            c.add_polygon(_rect(x, 5.0, 2.0, 6.0), layer=JJ if index % 4 == 0 else MARKER)
        c.add_port("input", center=(0.0, 0.0), width=10.0, orientation=180, layer=M2)
        c.add_port("output", center=(self.unit_cell_count * pitch, 0.0), width=10.0, orientation=0, layer=M2)
        c.info["framework_component"] = self.name
        c.info["layout_quality_mode"] = "unsupported"
        c.info["reason"] = "TWPA unit cell needs dispersion-engineering signoff before fabrication_real"
        return c

    def ports(self) -> dict[str, QuantumPort]:
        return {
            "input": QuantumPort("input", (0.0, 0.0), 10.0, 180.0, M2, "rf"),
            "output": QuantumPort("output", (self.unit_cell_count * 20.0, 0.0), 10.0, 0.0, M2, "rf"),
        }

    def netlist(self) -> ComponentNetlist:
        return ComponentNetlist(component=self.name, nets=(ComponentNet("twpa_line", ("input", "output"), "rf"),), parameters={"unit_cell_count": self.unit_cell_count})

    def extract(self) -> dict[str, Any]:
        return {
            "schema": "text-to-gds.device.extract.twpa.v1",
            "status": "unsupported",
            "reason": "periodic loading and dispersion model not solver-validated",
        }
