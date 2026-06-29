"""Josephson junction extraction from GDS geometry."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from text_to_gds.extraction.boolean_extract import _load_region, Finding
from text_to_gds.extraction.provenance import ExtractionProvenance
from text_to_gds.process import DEFAULT_PROCESS

Layer = tuple[int, int]

# Physical constants
_PHI0 = 2.067833848e-15  # Magnetic flux quantum (Wb)
_DEFAULT_JC_A_PER_M2 = 1e10  # 10 uA/um^2 default Jc

_JJ_LAYER = DEFAULT_PROCESS.layer("JJ")
_M1_LAYER = DEFAULT_PROCESS.layer("M1")
_M2_LAYER = DEFAULT_PROCESS.layer("M2")


@dataclass
class JJExtraction:
    """One extracted Josephson junction."""

    area_um2: float
    center_um: tuple[float, float]
    ic_ua: float
    lj_ph: float
    bottom_layer: Layer
    top_layer: Layer
    provenance: ExtractionProvenance


@dataclass
class SQUIDExtraction:
    """Extracted SQUID loop parameters."""

    junctions: list[JJExtraction]
    loop_perimeter_um: float
    loop_area_um2: float
    estimated_loop_inductance_ph: float
    provenance: ExtractionProvenance


def _ic_from_area(area_um2: float, jc_a_per_m2: float) -> float:
    """Ic = Jc * A, returns uA."""
    area_m2 = area_um2 * 1e-12
    return jc_a_per_m2 * area_m2 * 1e6  # convert A to uA


def _lj_from_ic(ic_ua: float) -> float:
    """Lj = Phi0 / (2*pi*Ic), returns pH."""
    ic_a = ic_ua * 1e-6
    if ic_a <= 0:
        return 0.0
    lj_h = _PHI0 / (2.0 * math.pi * ic_a)
    return lj_h * 1e12  # convert H to pH


def extract_junction_areas(
    gds_path: str | Path,
    jc_a_per_m2: float = _DEFAULT_JC_A_PER_M2,
    bottom_layer: Layer = _M1_LAYER,
    top_layer: Layer = _M2_LAYER,
    barrier_layer: Layer = _JJ_LAYER,
) -> list[JJExtraction]:
    """Find all M1 AND M2 overlaps within JJ barrier regions, extract per-junction parameters."""
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(gds_path))
    dbu = float(layout.dbu)

    m1 = _load_region(layout, bottom_layer)
    m2 = _load_region(layout, top_layer)
    jj = _load_region(layout, barrier_layer)

    # M1 AND M2 overlap
    overlap = m1 & m2
    # Restrict to JJ barrier regions if JJ layer is populated
    if not jj.is_empty():
        overlap &= jj

    junctions: list[JJExtraction] = []
    for poly in overlap.each():
        area_um2 = float(poly.area()) * dbu * dbu
        if area_um2 <= 0:
            continue
        bbox = poly.bbox()
        cx = (float(bbox.left) + float(bbox.right)) / 2.0 * dbu
        cy = (float(bbox.bottom) + float(bbox.top)) / 2.0 * dbu
        ic_ua = _ic_from_area(area_um2, jc_a_per_m2)
        lj_ph = _lj_from_ic(ic_ua)

        prov = ExtractionProvenance(
            method="extracted",
            source="klayout.db",
            formula="Ic=Jc*A; Lj=Phi0/(2*pi*Ic)",
            confidence=0.98,
            unit="um^2",
        )
        junctions.append(JJExtraction(
            area_um2=area_um2,
            center_um=(cx, cy),
            ic_ua=ic_ua,
            lj_ph=lj_ph,
            bottom_layer=bottom_layer,
            top_layer=top_layer,
            provenance=prov,
        ))
    return junctions


def verify_junction_count(
    gds_path: str | Path,
    expected_count: int,
    bottom_layer: Layer = _M1_LAYER,
    top_layer: Layer = _M2_LAYER,
    barrier_layer: Layer = _JJ_LAYER,
) -> Finding:
    """Check that the GDS contains exactly the expected number of junctions."""
    junctions = extract_junction_areas(
        gds_path,
        bottom_layer=bottom_layer,
        top_layer=top_layer,
        barrier_layer=barrier_layer,
    )
    actual = len(junctions)
    if actual == expected_count:
        return Finding(
            passed=True,
            message=f"Junction count matches: {actual}",
            severity="info",
        )
    return Finding(
        passed=False,
        message=f"Expected {expected_count} junction(s), found {actual}",
        severity="error",
        extra={"expected": expected_count, "actual": actual},
    )


def extract_squid_parameters(
    gds_path: str | Path,
    jc_a_per_m2: float = _DEFAULT_JC_A_PER_M2,
    bottom_layer: Layer = _M1_LAYER,
    top_layer: Layer = _M2_LAYER,
    barrier_layer: Layer = _JJ_LAYER,
    loop_layer: Layer = _M1_LAYER,
) -> SQUIDExtraction:
    """Extract SQUID parameters: two JJ areas + loop geometry."""
    import klayout.db as kdb

    junctions = extract_junction_areas(
        gds_path,
        jc_a_per_m2=jc_a_per_m2,
        bottom_layer=bottom_layer,
        top_layer=top_layer,
        barrier_layer=barrier_layer,
    )

    # Loop geometry from bottom electrode (M1) minus the junction regions
    layout = kdb.Layout()
    layout.read(str(gds_path))
    dbu = float(layout.dbu)

    loop_region = _load_region(layout, loop_layer)

    # The SQUID loop is approximated by the M1 region that encloses the JJs
    loop_bbox = loop_region.bbox()
    loop_perimeter_um = 2.0 * (
        float(loop_bbox.width()) * dbu + float(loop_bbox.height()) * dbu
    ) if not loop_region.is_empty() else 0.0
    loop_area_um2 = (
        float(loop_bbox.width()) * dbu * float(loop_bbox.height()) * dbu
    ) if not loop_region.is_empty() else 0.0

    # Estimated loop inductance: L ~ mu0 * perimeter / width (thin-film approx)
    mu0 = 1.25663706212e-6  # H/m
    # Use the narrower dimension as an effective width
    if not loop_region.is_empty():
        w_m = min(float(loop_bbox.width()), float(loop_bbox.height())) * dbu * 1e-6
        perimeter_m = loop_perimeter_um * 1e-6
        if w_m > 0:
            estimated_l_ph = mu0 * perimeter_m / w_m * 1e12
        else:
            estimated_l_ph = 0.0
    else:
        estimated_l_ph = 0.0

    prov = ExtractionProvenance(
        method="extracted",
        source="klayout.db",
        formula="L_loop ~ mu0 * perimeter / width (thin-film)",
        confidence=0.6,
        unit="pH",
    )
    return SQUIDExtraction(
        junctions=junctions,
        loop_perimeter_um=loop_perimeter_um,
        loop_area_um2=loop_area_um2,
        estimated_loop_inductance_ph=estimated_l_ph,
        provenance=prov,
    )
