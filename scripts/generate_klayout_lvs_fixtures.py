"""Generate connectivity-level partial-LVS golden fixtures."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import klayout.db as kdb

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "tests" / "fixtures" / "klayout_lvs"
DBU = 0.001
M1 = (1, 0)
TERM = (90, 0)


@dataclass(frozen=True)
class Fixture:
    name: str
    metal: list[kdb.Box]
    labels: dict[str, tuple[float, float]]
    reference_nets: list[dict[str, object]]
    expected_errors: tuple[str, ...]
    supported_structures: tuple[str, ...]
    top_cell: str = "TOP"


def um(value: float) -> int:
    return int(round(value / DBU))


def box(x1: float, y1: float, x2: float, y2: float) -> kdb.Box:
    return kdb.Box(um(x1), um(y1), um(x2), um(y2))


def ref(name: str, terminals: list[str]) -> dict[str, object]:
    return {"name": name, "terminals": terminals}


def fixtures() -> list[Fixture]:
    return [
        Fixture("idc_connectivity_pass", [box(0, 0, 10, 40), box(30, 0, 40, 40)], {"P": (5, 5), "N": (35, 5)}, [ref("P", ["P"]), ref("N", ["N"])], (), ("IDC",)),
        Fixture("idc_p_n_short", [box(0, 0, 40, 40)], {"P": (5, 5), "N": (35, 5)}, [ref("P", ["P"]), ref("N", ["N"])], ("SHORT",), ("IDC",)),
        Fixture("idc_disconnected_finger", [box(0, 0, 10, 40), box(30, 0, 40, 40), box(15, 20, 25, 22)], {"P": (5, 5), "N": (35, 5)}, [ref("P", ["P"]), ref("N", ["N"])], ("FLOATING_NET",), ("IDC",)),
        Fixture("idc_missing_terminal", [box(0, 0, 10, 40), box(30, 0, 40, 40)], {"P": (5, 5)}, [ref("P", ["P"]), ref("N", ["N"])], ("MISSING_TERMINAL",), ("IDC",)),
        Fixture("cpw_connectivity_pass", [box(0, 20, 80, 30), box(0, 0, 80, 10)], {"IN": (5, 25), "OUT": (75, 25), "GND_IN": (5, 5), "GND_OUT": (75, 5)}, [ref("SIGNAL", ["IN", "OUT"]), ref("GROUND", ["GND_IN", "GND_OUT"])], (), ("CPW",)),
        Fixture("cpw_signal_ground_short", [box(0, 0, 80, 30)], {"IN": (5, 25), "OUT": (75, 25), "GND_IN": (5, 5)}, [ref("SIGNAL", ["IN", "OUT"]), ref("GROUND", ["GND_IN"])], ("SHORT",), ("CPW",)),
        Fixture("cpw_broken_signal", [box(0, 20, 30, 30), box(50, 20, 80, 30), box(0, 0, 80, 10)], {"IN": (5, 25), "OUT": (75, 25), "GND_IN": (5, 5)}, [ref("SIGNAL", ["IN", "OUT"]), ref("GROUND", ["GND_IN"])], ("OPEN",), ("CPW",)),
        Fixture("cpw_missing_input_port", [box(0, 20, 80, 30), box(0, 0, 80, 10)], {"OUT": (75, 25), "GND_IN": (5, 5)}, [ref("SIGNAL", ["IN", "OUT"]), ref("GROUND", ["GND_IN"])], ("MISSING_TERMINAL",), ("CPW",)),
        Fixture("cpw_missing_output_port", [box(0, 20, 80, 30), box(0, 0, 80, 10)], {"IN": (5, 25), "GND_IN": (5, 5)}, [ref("SIGNAL", ["IN", "OUT"]), ref("GROUND", ["GND_IN"])], ("MISSING_TERMINAL",), ("CPW",)),
        Fixture("spiral_connectivity_pass", [box(0, 0, 80, 10)], {"A": (5, 5), "B": (75, 5)}, [ref("SPIRAL", ["A", "B"])], (), ("SPIRAL",)),
        Fixture("spiral_open_path", [box(0, 0, 30, 10), box(50, 0, 80, 10)], {"A": (5, 5), "B": (75, 5)}, [ref("SPIRAL", ["A", "B"])], ("OPEN",), ("SPIRAL",)),
        Fixture("spiral_adjacent_turn_short", [box(0, 0, 80, 10)], {"A": (5, 5), "B": (75, 5), "TURN": (40, 5)}, [ref("SPIRAL", ["A", "B"]), ref("ADJACENT_TURN", ["TURN"])], ("SHORT",), ("SPIRAL",)),
        Fixture("resonator_connectivity_pass", [box(0, 0, 80, 10), box(0, 30, 20, 40)], {"GND": (5, 5), "OPEN": (75, 5), "COUPLER": (10, 35)}, [ref("RESONATOR", ["GND", "OPEN"]), ref("COUPLER", ["COUPLER"])], (), ("RESONATOR",)),
        Fixture("resonator_open_end_short", [box(0, 0, 80, 10)], {"GND": (5, 5), "OPEN": (75, 5)}, [ref("GROUND_END", ["GND"]), ref("OPEN_END", ["OPEN"])], ("SHORT",), ("RESONATOR",)),
        Fixture("resonator_ground_end_open", [box(0, 0, 80, 10)], {"OPEN": (75, 5)}, [ref("GROUND_END", ["GND"]), ref("OPEN_END", ["OPEN"])], ("MISSING_TERMINAL",), ("RESONATOR",)),
    ]


def write_gds(fixture: Fixture) -> Path:
    layout = kdb.Layout()
    layout.dbu = DBU
    top = layout.create_cell(fixture.top_cell)
    metal_layer = layout.layer(*M1)
    terminal_layer = layout.layer(*TERM)
    for shape in fixture.metal:
        top.shapes(metal_layer).insert(shape)
    for label, (x, y) in sorted(fixture.labels.items()):
        top.shapes(terminal_layer).insert(kdb.Text(label, kdb.Trans(um(x), um(y))))
    path = OUT / f"{fixture.name}.gds"
    layout.write(str(path))
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for fixture in fixtures():
        path = write_gds(fixture)
        rows.append(
            {
                "name": fixture.name,
                "path": path.relative_to(REPO).as_posix(),
                "top_cell": fixture.top_cell,
                "gds_hash": sha256(path),
                "reference_nets": fixture.reference_nets,
                "expected_errors": list(fixture.expected_errors),
                "supported_structures": list(fixture.supported_structures),
                "conductor_layers": {"M1": list(M1)},
                "terminal_layer": list(TERM),
            }
        )
    manifest = {
        "schema": "textlayout.klayout-partial-lvs-fixtures.v1",
        "unsupported_structures": [],
        "unsupported_devices": ["capacitance", "inductance", "josephson_junction", "vias"],
        "fixtures": rows,
    }
    (OUT / "expectations.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
