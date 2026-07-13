"""Generate committed KLayout DRC golden fixtures.

These fixtures exercise the supported typed-PDK DRC subset. They are not a
foundry deck and do not establish fabrication readiness.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import klayout.db as kdb

from textlayout.pdk.klayout_drc import run_drc, to_lydrc
from textlayout.pdk.loader import write_pdk
from textlayout.pdk.models import (
    PDK,
    PDKEnclosure,
    PDKGrid,
    PDKJunctionProcess,
    PDKLayer,
    PDKOverlap,
    PDKSeparation,
    PDKSubstrate,
)

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "tests" / "fixtures" / "klayout_drc"
DBU = 0.001


@dataclass(frozen=True)
class Fixture:
    name: str
    shapes: dict[str, list[kdb.Box | kdb.Polygon]]
    expected_rule_ids: tuple[str, ...]
    min_expected_violations: int
    max_unexpected_violations: int = 0
    top_cell: str = "TOP"


def um(value: float) -> int:
    return int(round(value / DBU))


def box(x1: float, y1: float, x2: float, y2: float) -> kdb.Box:
    return kdb.Box(um(x1), um(y1), um(x2), um(y2))


def notch() -> kdb.Polygon:
    return kdb.Polygon(
        [
            kdb.Point(um(0), um(0)),
            kdb.Point(um(10), um(0)),
            kdb.Point(um(10), um(10)),
            kdb.Point(um(6), um(10)),
            kdb.Point(um(6), um(5)),
            kdb.Point(um(4.8), um(5)),
            kdb.Point(um(4.8), um(10)),
            kdb.Point(um(0), um(10)),
        ]
    )


def pdk() -> PDK:
    return PDK(
        name="klayout_signoff_fixture_pdk",
        version="0.1.0",
        foundry_validated=False,
        calibration_status="illustrative",
        source="tests/fixtures/klayout_drc/pdk.yaml",
        grid=PDKGrid(grid_nm=1.0, default_min_spacing_um=2.0, default_min_width_um=2.0),
        substrate=PDKSubstrate(material="silicon", epsilon_r=11.9, loss_tangent=1e-6),
        junction_process=PDKJunctionProcess(
            target_jc_ua_per_um2=1.0,
            jc_sigma_pct=5.0,
            min_junction_area_um2=0.04,
        ),
        layers=[
            PDKLayer(name="M1", purpose="metal", gds_layer=1, min_width_um=2.0, min_spacing_um=2.0),
            PDKLayer(name="IDC_FINGER", purpose="metal", gds_layer=11, min_width_um=2.0, min_spacing_um=2.0),
            PDKLayer(name="IDC_BUS", purpose="metal", gds_layer=12, min_width_um=4.0, min_spacing_um=2.0),
            PDKLayer(name="IDC_P", purpose="metal", gds_layer=13, min_width_um=2.0, min_spacing_um=2.0),
            PDKLayer(name="IDC_N", purpose="metal", gds_layer=14, min_width_um=2.0, min_spacing_um=2.0),
            PDKLayer(name="CPW_SIGNAL", purpose="metal", gds_layer=21, min_width_um=10.0, min_spacing_um=2.0),
            PDKLayer(name="CPW_GROUND", purpose="ground", gds_layer=22, min_width_um=10.0, min_spacing_um=2.0),
            PDKLayer(name="SPIRAL_TRACE", purpose="metal", gds_layer=31, min_width_um=3.0, min_spacing_um=3.0),
            PDKLayer(name="JJ", purpose="junction", gds_layer=41, min_width_um=0.05, min_spacing_um=0.05),
        ],
        enclosures=[PDKEnclosure(inner="JJ", outer="M1", min_um=0.2)],
        overlaps=[PDKOverlap(a="JJ", b="M1", min_um=0.2)],
        separations=[
            PDKSeparation(
                a="IDC_P",
                b="IDC_N",
                min_um=2.0,
                rule_id="IDC.NO_UNINTENDED_BRIDGE",
                description="IDC P and N electrodes must remain isolated.",
            ),
            PDKSeparation(
                a="CPW_SIGNAL",
                b="CPW_GROUND",
                min_um=6.0,
                rule_id="CPW.MIN_SIGNAL_GROUND_GAP",
                description="CPW signal-ground gap must be at least 6 um.",
            ),
        ],
    )


LAYER_GDS = {
    "M1": (1, 0),
    "IDC_FINGER": (11, 0),
    "IDC_BUS": (12, 0),
    "IDC_P": (13, 0),
    "IDC_N": (14, 0),
    "CPW_SIGNAL": (21, 0),
    "CPW_GROUND": (22, 0),
    "SPIRAL_TRACE": (31, 0),
    "JJ": (41, 0),
}


def fixtures() -> list[Fixture]:
    valid_idc = {
        "IDC_BUS": [box(0, 0, 4, 40), box(30, 0, 34, 40)],
        "IDC_FINGER": [box(4, 2, 22, 4), box(12, 8, 30, 10), box(4, 14, 22, 16)],
        "IDC_P": [box(0, 0, 4, 40), box(4, 2, 22, 4), box(4, 14, 22, 16)],
        "IDC_N": [box(30, 0, 34, 40), box(12, 8, 30, 10)],
    }
    valid_cpw = {
        "CPW_SIGNAL": [box(0, 20, 80, 30)],
        "CPW_GROUND": [box(0, 0, 80, 10), box(0, 40, 80, 50)],
    }
    valid_spiral = {
        "SPIRAL_TRACE": [
            box(0, 0, 40, 3),
            box(37, 3, 40, 40),
            box(8, 37, 37, 40),
            box(8, 12, 11, 37),
            box(11, 12, 29, 15),
        ]
    }
    valid_resonator = {
        "CPW_SIGNAL": [box(0, 20, 80, 30)],
        "CPW_GROUND": [box(0, 0, 80, 10), box(0, 40, 80, 50)],
        "M1": [box(0, 55, 10, 65)],
    }
    return [
        Fixture("valid_idc", valid_idc, (), 0),
        Fixture("valid_cpw", valid_cpw, (), 0),
        Fixture("valid_spiral", valid_spiral, (), 0),
        Fixture("valid_resonator", valid_resonator, (), 0),
        Fixture("invalid_idc_finger_width", {**valid_idc, "IDC_FINGER": [box(4, 2, 22, 3)]}, ("IDC.MIN_FINGER_WIDTH",), 1),
        Fixture("invalid_idc_finger_gap", {**valid_idc, "IDC_FINGER": [box(4, 2, 22, 4), box(4, 5, 22, 7)]}, ("IDC.MIN_FINGER_SPACING",), 1),
        Fixture("invalid_idc_bridge", {**valid_idc, "IDC_P": [box(0, 0, 20, 5)], "IDC_N": [box(19, 0, 34, 5)]}, ("IDC.NO_UNINTENDED_BRIDGE",), 1),
        Fixture("invalid_idc_bus_width", {**valid_idc, "IDC_BUS": [box(0, 0, 2, 40)]}, ("IDC.MIN_BUS_WIDTH",), 1),
        Fixture("invalid_cpw_signal_width", {"CPW_SIGNAL": [box(0, 20, 80, 25)], "CPW_GROUND": valid_cpw["CPW_GROUND"]}, ("CPW.MIN_CENTER_CONDUCTOR_WIDTH",), 1),
        Fixture("invalid_cpw_gap", {"CPW_SIGNAL": [box(0, 20, 80, 30)], "CPW_GROUND": [box(0, 0, 80, 17), box(0, 40, 80, 50)]}, ("CPW.MIN_SIGNAL_GROUND_GAP",), 1),
        Fixture("invalid_cpw_signal_ground_short", {"CPW_SIGNAL": [box(0, 20, 80, 30)], "CPW_GROUND": [box(0, 0, 80, 22)]}, ("CPW.MIN_SIGNAL_GROUND_GAP",), 1),
        Fixture("invalid_cpw_ground_discontinuity", {"CPW_SIGNAL": [box(0, 20, 80, 30)], "CPW_GROUND": [box(0, 0, 80, 5), box(0, 40, 80, 50)]}, ("klayout_signoff_fixture_pdk.min_width.CPW_GROUND",), 1),
        Fixture("invalid_spiral_trace_width", {"SPIRAL_TRACE": [box(0, 0, 40, 2)]}, ("SPIRAL.MIN_TRACE_WIDTH",), 1),
        Fixture("invalid_spiral_turn_spacing", {"SPIRAL_TRACE": [box(0, 0, 40, 3), box(0, 5, 40, 8)]}, ("SPIRAL.MIN_TURN_SPACING",), 1),
        Fixture("invalid_junction_area", {"JJ": [box(0, 0, 0.1, 0.1)]}, ("JJ.MIN_AREA",), 1),
        Fixture("invalid_junction_overlap", {"JJ": [box(1.9, 1, 2.9, 2)], "M1": [box(0, 0, 2, 3)]}, ("JJ.MIN_LEAD_OVERLAP",), 1),
        Fixture("invalid_floating_conductor", {"M1": [box(0, 0, 1, 10)]}, ("klayout_signoff_fixture_pdk.min_width.M1",), 1),
        Fixture("invalid_minimum_area", {"M1": [box(0, 0, 0.5, 0.5)]}, ("klayout_signoff_fixture_pdk.min_area.M1", "klayout_signoff_fixture_pdk.min_width.M1"), 1),
        Fixture("invalid_notch", {"M1": [notch()]}, ("klayout_signoff_fixture_pdk.notch.M1", "klayout_signoff_fixture_pdk.min_spacing.M1"), 1),
    ]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_gds(fixture: Fixture) -> Path:
    layout = kdb.Layout()
    layout.dbu = DBU
    top = layout.create_cell(fixture.top_cell)
    for layer_name, shapes in fixture.shapes.items():
        layer, datatype = LAYER_GDS[layer_name]
        index = layout.layer(layer, datatype)
        for shape in shapes:
            top.shapes(index).insert(shape)
    path = OUT / f"{fixture.name}.gds"
    layout.write(str(path))
    return path


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    process = pdk()
    write_pdk(process, OUT / "pdk.yaml")
    runset = to_lydrc(process)
    runset_path = OUT / "compiled_rules.lydrc"
    runset_path.write_text(runset + "\n", encoding="ascii")
    pdk_hash = hashlib.sha256(
        json.dumps(process.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    runset_hash = hashlib.sha256(runset.encode("utf-8")).hexdigest()
    rows = []
    for fixture in fixtures():
        gds = write_gds(fixture)
        report = run_drc(process, gds, top_cell=fixture.top_cell)
        rows.append(
            {
                "name": fixture.name,
                "path": gds.relative_to(REPO).as_posix(),
                "top_cell": fixture.top_cell,
                "gds_hash": sha256(gds),
                "pdk_hash": pdk_hash,
                "runset_hash": runset_hash,
                "expected_rule_ids": list(fixture.expected_rule_ids),
                "min_expected_violation_count": fixture.min_expected_violations,
                "max_unexpected_violations": fixture.max_unexpected_violations,
                "observed_rule_ids": sorted({violation.rule_id for violation in report.violations}),
            }
        )
    manifest = {
        "schema": "textlayout.klayout-drc-fixtures.v1",
        "pdk": "tests/fixtures/klayout_drc/pdk.yaml",
        "runset": "tests/fixtures/klayout_drc/compiled_rules.lydrc",
        "pdk_hash": pdk_hash,
        "runset_hash": runset_hash,
        "fixtures": rows,
    }
    (OUT / "expectations.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
