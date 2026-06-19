from __future__ import annotations

import math

import gdsfactory as gf

from text_to_gds.process import JJ, M1, M2, M3, MARKER, require_positive
from text_to_gds.traveling_wave import ERICKSON_KIT_REGIONS, PLANAT_SAMPLES


def _rectangle(cx: float, cy: float, width: float, height: float) -> list[tuple[float, float]]:
    return [
        (cx - width / 2.0, cy - height / 2.0),
        (cx + width / 2.0, cy - height / 2.0),
        (cx + width / 2.0, cy + height / 2.0),
        (cx - width / 2.0, cy + height / 2.0),
    ]


def _stwpa_period(
    *,
    period_squids: int,
    pitch_um: float,
    junction_width_um: float,
    average_height_um: float,
    modulation: float,
) -> gf.Component:
    period = gf.Component()
    period_length = period_squids * pitch_um
    period.add_polygon(_rectangle(period_length / 2.0, 0.0, period_length, 0.5), layer=M1)
    reciprocal = 2.0 * math.pi / period_squids
    for index in range(period_squids):
        x = (index + 0.5) * pitch_um
        height = average_height_um * (
            1.0 + modulation * math.cos(reciprocal * (index + 0.5))
        )
        # The two barrier rectangles are the two junctions of one SQUID.
        for y in (-height / 4.0, height / 4.0):
            period.add_polygon(
                _rectangle(x, y, junction_width_um, max(height / 2.0, 0.01)),
                layer=JJ,
            )
        period.add_polygon(_rectangle(x, 0.0, junction_width_um * 1.8, height), layer=M2)
    return period


@gf.cell
def photonic_crystal_stwpa(
    sample: str = "A",
    junction_width_um: float = 0.45,
    average_junction_height_um: float = 12.0,
    dielectric_thickness_nm: float = 28.0,
    ground_thickness_um: float = 1.0,
) -> gf.Component:
    """Planat-style periodically modulated SQUID-chain STWPA layout.

    The repeated hierarchy preserves all paper sample A/B periods without flattening
    thousands of identical SQUID cells into the top-level GDS cell.
    """
    key = sample.upper()
    if key not in PLANAT_SAMPLES:
        raise ValueError(f"Unknown Planat sample {sample!r}; choose A or B")
    for name, value in {
        "junction_width_um": junction_width_um,
        "average_junction_height_um": average_junction_height_um,
        "dielectric_thickness_nm": dielectric_thickness_nm,
        "ground_thickness_um": ground_thickness_um,
    }.items():
        require_positive(name, value)
    p = PLANAT_SAMPLES[key]
    squid_count = int(p["squid_count"])
    period_squids = int(p["period_squids"])
    pitch = float(p["pitch_um"])
    modulation = float(p["junction_modulation"])
    period = _stwpa_period(
        period_squids=period_squids,
        pitch_um=pitch,
        junction_width_um=junction_width_um,
        average_height_um=average_junction_height_um,
        modulation=modulation,
    )
    c = gf.Component()
    period_count, remainder = divmod(squid_count, period_squids)
    period_length = period_squids * pitch
    for index in range(period_count):
        ref = c.add_ref(period)
        ref.move((index * period_length, 0.0))
    if remainder:
        remainder_cell = _stwpa_period(
            period_squids=remainder,
            pitch_um=pitch,
            junction_width_um=junction_width_um,
            average_height_um=average_junction_height_um,
            modulation=modulation,
        )
        ref = c.add_ref(remainder_cell)
        ref.move((period_count * period_length, 0.0))

    length = squid_count * pitch
    footprint_height = 13.0
    c.add_polygon(_rectangle(length / 2.0, 0.0, length, footprint_height), layer=M3)
    c.add_port(
        name="rf_in",
        center=(0.0, 0.0),
        width=0.5,
        orientation=180.0,
        layer=M1,
        port_type="electrical",
    )
    c.add_port(
        name="rf_out",
        center=(length, 0.0),
        width=0.5,
        orientation=0.0,
        layer=M1,
        port_type="electrical",
    )
    c.add_label(f"Planat STWPA sample {key}", position=(length / 2.0, 0.0), layer=MARKER)
    c.info["device_type"] = "photonic_crystal_stwpa"
    c.info["paper_reference"] = "PhysRevX.10.021021"
    c.info["sample"] = key
    c.info["squid_count"] = squid_count
    c.info["junction_count"] = 2 * squid_count
    c.info["period_squids"] = period_squids
    c.info["period_count"] = period_count
    c.info["pitch_um"] = pitch
    c.info["length_um"] = length
    c.info["footprint_height_um"] = footprint_height
    c.info["junction_width_um"] = junction_width_um
    c.info["average_junction_height_um"] = average_junction_height_um
    c.info["junction_modulation"] = modulation
    c.info["ground_modulation"] = float(p["ground_modulation"])
    c.info["dielectric_thickness_nm"] = dielectric_thickness_nm
    c.info["ground_thickness_um"] = ground_thickness_um
    c.info["reported_gap_center_ghz"] = float(p["reported_gap_center_ghz"])
    c.info["reported_gap_width_ghz"] = float(p["reported_gap_width_ghz"])
    c.info["layers"] = {"chain": M1, "squid_top": M2, "junction": JJ, "ground": M3}
    return c


@gf.cell
def periodically_loaded_kit_unit_cell(
    narrow_width_um: float = 2.0,
    loaded_width_um: float = 6.0,
    gap_um: float = 2.0,
) -> gf.Component:
    """Erickson-Pappas Table-II seven-region KIT periodic loading cell."""
    for name, value in {
        "narrow_width_um": narrow_width_um,
        "loaded_width_um": loaded_width_um,
        "gap_um": gap_um,
    }.items():
        require_positive(name, value)
    c = gf.Component()
    x = 0.0
    for index, (length, inductance, capacitance) in enumerate(ERICKSON_KIT_REGIONS, start=1):
        width = narrow_width_um if inductance > 1.5 else loaded_width_um
        c.add_polygon(_rectangle(x + length / 2.0, 0.0, length, width), layer=M2)
        c.add_label(f"r{index}", position=(x + length / 2.0, 0.0), layer=MARKER)
        x += length
    c.add_port(
        name="rf_in",
        center=(0.0, 0.0),
        width=narrow_width_um,
        orientation=180.0,
        layer=M2,
        port_type="electrical",
    )
    c.add_port(
        name="rf_out",
        center=(x, 0.0),
        width=narrow_width_um,
        orientation=0.0,
        layer=M2,
        port_type="electrical",
    )
    c.info["device_type"] = "periodically_loaded_kit_unit_cell"
    c.info["paper_reference"] = "arXiv:1612.00365v2"
    c.info["region_count"] = len(ERICKSON_KIT_REGIONS)
    c.info["unit_cell_length_um"] = x
    c.info["narrow_width_um"] = narrow_width_um
    c.info["loaded_width_um"] = loaded_width_um
    c.info["gap_um"] = gap_um
    c.info["regions"] = [
        {
            "length_um": length,
            "inductance_ph_per_um": inductance,
            "capacitance_ff_per_um": capacitance,
        }
        for length, inductance, capacitance in ERICKSON_KIT_REGIONS
    ]
    c.info["layers"] = {"kit_trace": M2, "marker": MARKER}
    return c
