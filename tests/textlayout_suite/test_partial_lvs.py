"""Connectivity-level partial LVS fixture tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import klayout.db as kdb

from textlayout.pdk.lvs import run_partial_connectivity_lvs

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "klayout_lvs"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest() -> dict:
    return json.loads((FIXTURE_ROOT / "expectations.json").read_text(encoding="ascii"))


def _run(fixture: dict, path: Path | None = None) -> dict:
    return run_partial_connectivity_lvs(
        path or REPO_ROOT / fixture["path"],
        reference_nets=fixture["reference_nets"],
        conductor_layers={
            name: tuple(values) for name, values in fixture["conductor_layers"].items()
        },
        terminal_layer=tuple(fixture["terminal_layer"]),
        supported_structures=fixture["supported_structures"],
        unsupported_structures=_manifest()["unsupported_structures"],
        unsupported_devices=_manifest()["unsupported_devices"],
        top_cell=fixture["top_cell"],
    )


def _error_classes(report: dict) -> set[str]:
    classes: set[str] = set()
    if report["opens"]:
        classes.add("OPEN")
    if report["shorts"]:
        classes.add("SHORT")
    if report["floating_nets"]:
        classes.add("FLOATING_NET")
    if report["missing_terminals"]:
        classes.add("MISSING_TERMINAL")
    if report["extra_terminals"]:
        classes.add("EXTRA_TERMINAL")
    if report["terminal_mismatches"]:
        classes.add("TERMINAL_MISMATCH")
    return classes


def test_committed_partial_lvs_fixtures_match_expectations() -> None:
    for fixture in _manifest()["fixtures"]:
        gds = REPO_ROOT / fixture["path"]
        assert gds.is_file(), fixture["path"]
        assert _sha256(gds) == fixture["gds_hash"]
        report = _run(fixture)
        assert report["scope"] == "connectivity_partial_lvs"
        assert report["full_lvs_pass"] is False
        expected = set(fixture["expected_errors"])
        if expected:
            assert expected <= _error_classes(report), fixture["name"]
            assert report["passed"] is False
        else:
            assert _error_classes(report) == set(), fixture["name"]
            assert report["passed"] is True


def test_positive_cpw_has_expected_extracted_nets_and_terminals() -> None:
    fixture = next(item for item in _manifest()["fixtures"] if item["name"] == "cpw_connectivity_pass")
    report = _run(fixture)
    extracted = {tuple(net["terminals"]) for net in report["extracted_nets"]}
    assert ("GND_IN", "GND_OUT") in extracted
    assert ("IN", "OUT") in extracted
    assert len(report["extracted_nets"]) == 2


def test_connectivity_invariant_under_flattening_polygon_order_and_dbu(tmp_path: Path) -> None:
    fixture = next(item for item in _manifest()["fixtures"] if item["name"] == "cpw_connectivity_pass")
    source = REPO_ROOT / fixture["path"]
    baseline = _run(fixture)["extracted_nets"]

    flattened = tmp_path / "flattened.gds"
    reordered = tmp_path / "reordered.gds"
    dbu_changed = tmp_path / "dbu_changed.gds"
    _write_variant(source, flattened, mode="flattened", dbu=0.001)
    _write_variant(source, reordered, mode="reordered", dbu=0.001)
    _write_variant(source, dbu_changed, mode="reordered", dbu=0.002)

    for variant in (flattened, reordered, dbu_changed):
        observed = _run(fixture, variant)["extracted_nets"]
        assert _canonical_nets(observed) == _canonical_nets(baseline)


def _canonical_nets(nets: list[dict]) -> list[tuple[tuple[str, ...], str]]:
    return sorted((tuple(net["terminals"]), net["layer"]) for net in nets)


def _write_variant(source: Path, target: Path, *, mode: str, dbu: float) -> None:
    original = kdb.Layout()
    original.read(str(source))
    top = original.top_cell()
    assert top is not None
    layout = kdb.Layout()
    layout.dbu = dbu
    cell = layout.create_cell("TOP")
    scale = original.dbu / dbu
    shapes: list[tuple[tuple[int, int], kdb.Shape]] = []
    for index in original.layer_indexes():
        info = original.get_info(index)
        iterator = top.begin_shapes_rec(index)
        while not iterator.at_end():
            shapes.append(((info.layer, info.datatype), iterator.shape()))
            iterator.next()
    if mode == "reordered":
        shapes = list(reversed(shapes))
    for (layer, datatype), shape in shapes:
        out_index = layout.layer(layer, datatype)
        if shape.is_box():
            box = shape.box
            cell.shapes(out_index).insert(
                kdb.Box(
                    round(box.left * scale),
                    round(box.bottom * scale),
                    round(box.right * scale),
                    round(box.top * scale),
                )
            )
        elif shape.is_text():
            text = shape.text
            cell.shapes(out_index).insert(
                kdb.Text(
                    text.string,
                    kdb.Trans(
                        round(text.trans.disp.x * scale),
                        round(text.trans.disp.y * scale),
                    ),
                )
            )
    layout.write(str(target))
