"""KLayout DRC compiled from the typed PDK, run against real GDS.

Every layout here is built with klayout.db and written to a real .gds, so the
checks run through KLayout's own Region engine rather than a reimplementation of
it. The violations are deliberate and hand-computable.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import klayout.db as kdb
import pytest
from pydantic import ValidationError

from textlayout.pdk.klayout_drc import UNSUPPORTED_RULES, run_drc, to_lydrc
from textlayout.pdk.loader import load_pdk
from textlayout.pdk.models import (
    PDK,
    PDKEnclosure,
    PDKGrid,
    PDKJunctionProcess,
    PDKLayer,
    PDKOverlap,
    PDKSeparation,
    PDKSubstrate,
    RuleRequirement,
)

GRID = PDKGrid(grid_nm=1.0, default_min_spacing_um=1.0, default_min_width_um=1.0)
SUBSTRATE = PDKSubstrate(material="silicon", epsilon_r=11.45, loss_tangent=1e-6)
REPO_ROOT = Path(__file__).resolve().parents[2]


def _pdk(**overrides) -> PDK:
    payload = {
        "name": "test_pdk",
        "version": "0.1",
        "foundry_validated": False,
        "calibration_status": "illustrative",
        "source": "synthetic, for tests",
        "grid": GRID,
        "layers": [
            PDKLayer(name="metal", purpose="metal", gds_layer=1, min_width_um=1.0, min_spacing_um=2.0),
        ],
        "substrate": SUBSTRATE,
    }
    payload.update(overrides)
    return PDK(**payload)  # type: ignore[arg-type]


def _gds(tmp_path: Path, shapes: dict[tuple[int, int], list[kdb.Box]], name: str = "TOP") -> Path:
    layout = kdb.Layout()
    layout.dbu = 0.001
    top = layout.create_cell(name)
    for (layer, datatype), boxes in shapes.items():
        index = layout.layer(layer, datatype)
        for box in boxes:
            top.shapes(index).insert(box)
    path = tmp_path / "layout.gds"
    layout.write(str(path))
    return path


def _um(value: float) -> int:
    return int(round(value * 1000))


class TestMinWidthAndSpacing:
    def test_a_clean_layout_passes(self, tmp_path: Path) -> None:
        gds = _gds(tmp_path, {(1, 0): [kdb.Box(0, 0, _um(5), _um(5))]})
        report = run_drc(_pdk(), gds)
        assert report.passed
        assert report.violations == []

    def test_a_narrow_shape_violates_min_width(self, tmp_path: Path) -> None:
        gds = _gds(tmp_path, {(1, 0): [kdb.Box(0, 0, _um(0.4), _um(5))]})
        report = run_drc(_pdk(), gds)
        assert not report.passed
        violation = next(v for v in report.violations if v.rule == "min_width")
        assert violation.layer == "metal"
        assert violation.required_um == 1.0
        assert violation.sample_bbox_um is not None

    def test_two_close_shapes_violate_min_spacing(self, tmp_path: Path) -> None:
        gds = _gds(
            tmp_path,
            {(1, 0): [kdb.Box(0, 0, _um(5), _um(5)), kdb.Box(_um(6), 0, _um(11), _um(5))]},
        )  # 1 um apart, rule is 2 um
        report = run_drc(_pdk(), gds)
        assert any(v.rule == "min_spacing" for v in report.violations)

    def test_an_empty_layer_skips_with_a_reason_rather_than_passing(self, tmp_path: Path) -> None:
        gds = _gds(tmp_path, {(9, 0): [kdb.Box(0, 0, _um(5), _um(5))]})
        report = run_drc(_pdk(), gds)
        skipped = [c for c in report.checks if c.rule == "min_width" and not c.ran]
        assert skipped and "no geometry" in (skipped[0].skip_reason or "")


class TestCoverageIsNotSilence:
    def test_geometry_on_an_undeclared_layer_is_a_coverage_gap(self, tmp_path: Path) -> None:
        """Shapes the PDK does not know about are unchecked, not clean."""
        gds = _gds(
            tmp_path,
            {(1, 0): [kdb.Box(0, 0, _um(5), _um(5))], (77, 3): [kdb.Box(0, 0, _um(5), _um(5))]},
        )
        report = run_drc(_pdk(), gds)
        assert report.passed  # no rule fired...
        assert not report.coverage_complete  # ...but not everything was looked at
        assert report.undeclared_layers == ["77/3"]
        assert "does not declare" in (report.blocking_reason() or "")

    def test_an_empty_undeclared_layer_is_not_a_gap(self, tmp_path: Path) -> None:
        layout = kdb.Layout()
        layout.dbu = 0.001
        top = layout.create_cell("TOP")
        top.shapes(layout.layer(1, 0)).insert(kdb.Box(0, 0, _um(5), _um(5)))
        layout.layer(88, 0)  # declared in the file, carries nothing
        path = tmp_path / "layout.gds"
        layout.write(str(path))
        assert run_drc(_pdk(), path).coverage_complete

    def test_the_rules_this_engine_cannot_check_are_named(self, tmp_path: Path) -> None:
        gds = _gds(tmp_path, {(1, 0): [kdb.Box(0, 0, _um(5), _um(5))]})
        report = run_drc(_pdk(), gds)
        assert set(report.unsupported_rules) == set(UNSUPPORTED_RULES)
        assert "antenna_ratio" in report.unsupported_rules
        assert "min_area" not in report.unsupported_rules
        assert "notch" not in report.unsupported_rules


class TestRequiredLayerAndMandatoryRules:
    def test_missing_required_layer_is_blocking(self, tmp_path: Path) -> None:
        pdk = _pdk(
            layers=[
                PDKLayer(
                    name="metal",
                    purpose="metal",
                    gds_layer=1,
                    min_width_um=1.0,
                    min_spacing_um=1.0,
                    required=True,
                ),
            ]
        )
        gds = _gds(tmp_path, {(90, 0): [kdb.Box(0, 0, _um(5), _um(5))]})
        report = run_drc(pdk, gds)
        assert not report.coverage_complete
        violation = next(v for v in report.violations if v.rule_id == "PDK.REQUIRED_LAYER_MISSING")
        assert violation.blocking is True
        assert violation.mandatory is True

    def test_missing_optional_layer_is_nonblocking_skip(self, tmp_path: Path) -> None:
        pdk = _pdk(
            layers=[
                PDKLayer(
                    name="bridge",
                    purpose="metal",
                    gds_layer=7,
                    min_width_um=1.0,
                    min_spacing_um=1.0,
                    required=False,
                    required_when="crossover exists",
                ),
            ]
        )
        gds = _gds(tmp_path, {(90, 0): [kdb.Box(0, 0, _um(5), _um(5))]})
        report = run_drc(pdk, gds)
        skip = next(check for check in report.checks if check.rule == "min_width")
        assert skip.skip_kind == "skipped_optional_rule"
        assert skip.mandatory is False

    def test_skipped_mandatory_rule_blocks_signoff(self, tmp_path: Path) -> None:
        pdk = _pdk(
            foundry_validated=True,
            calibration_status="foundry_calibrated",
            layers=[
                PDKLayer(
                    name="metal",
                    purpose="metal",
                    gds_layer=1,
                    min_width_um=0.1,
                    min_spacing_um=0.1,
                    min_density_fraction=0.2,
                )
            ],
            density_window_um=50.0,
        )
        gds = _gds(tmp_path, {(1, 0): [kdb.Box(0, 0, _um(5), _um(5))]})
        report = run_drc(pdk, gds, deck_fixture_validated=True)
        assert not report.mandatory_checks_complete
        assert report.signoff_ready is False

    def test_unsupported_mandatory_rule_blocks_signoff(self, tmp_path: Path) -> None:
        pdk = _pdk(
            foundry_validated=True,
            calibration_status="foundry_calibrated",
            rule_requirements=[
                RuleRequirement(rule_family="floating_conductor", mandatory=True),
            ],
        )
        gds = _gds(tmp_path, {(1, 0): [kdb.Box(0, 0, _um(5), _um(5))]})
        report = run_drc(pdk, gds, deck_fixture_validated=True)
        assert "floating_conductor" in report.unsupported_mandatory_rules
        assert report.signoff_ready is False


class TestSignoffIsStricterThanPassing:
    def test_an_illustrative_pdk_can_never_sign_off(self, tmp_path: Path) -> None:
        gds = _gds(tmp_path, {(1, 0): [kdb.Box(0, 0, _um(5), _um(5))]})
        report = run_drc(_pdk(), gds)
        assert report.passed and report.coverage_complete
        assert report.signoff_ready is False
        assert "illustrative" in (report.blocking_reason() or "")

    def test_a_foundry_calibrated_clean_python_run_is_not_standalone_signoff(self, tmp_path: Path) -> None:
        pdk = _pdk(foundry_validated=True, calibration_status="foundry_calibrated")
        gds = _gds(tmp_path, {(1, 0): [kdb.Box(0, 0, _um(5), _um(5))]})
        report = run_drc(pdk, gds)
        assert report.passed and report.coverage_complete
        assert report.signoff_ready is False
        assert "standalone DRC deck" in (report.blocking_reason() or "")

    def test_a_foundry_calibrated_clean_run_with_deck_evidence_signs_off(self, tmp_path: Path) -> None:
        pdk = _pdk(foundry_validated=True, calibration_status="foundry_calibrated")
        gds = _gds(tmp_path, {(1, 0): [kdb.Box(0, 0, _um(5), _um(5))]})
        report = run_drc(pdk, gds, deck_fixture_validated=True)
        assert report.signoff_ready is True
        assert report.blocking_reason() is None

    def test_violations_outrank_calibration_in_the_blocking_reason(self, tmp_path: Path) -> None:
        pdk = _pdk(foundry_validated=True, calibration_status="foundry_calibrated")
        gds = _gds(tmp_path, {(1, 0): [kdb.Box(0, 0, _um(0.4), _um(5))]})
        report = run_drc(pdk, gds)
        assert "DRC rule(s) violated" in (report.blocking_reason() or "")


class TestTwoLayerRules:
    def _pdk(self) -> PDK:
        return _pdk(
            layers=[
                PDKLayer(name="metal", purpose="metal", gds_layer=1, min_width_um=0.1, min_spacing_um=0.1),
                PDKLayer(name="via", purpose="via", gds_layer=2, min_width_um=0.1, min_spacing_um=0.1),
            ],
            enclosures=[PDKEnclosure(inner="via", outer="metal", min_um=0.5)],
            overlaps=[PDKOverlap(a="metal", b="via", min_um=0.5)],
        )

    def test_insufficient_enclosure_is_caught(self, tmp_path: Path) -> None:
        gds = _gds(
            tmp_path,
            {
                (1, 0): [kdb.Box(0, 0, _um(2.2), _um(2.2))],
                (2, 0): [kdb.Box(_um(0.1), _um(0.1), _um(2.1), _um(2.1))],  # 0.1 um margin
            },
        )
        report = run_drc(self._pdk(), gds)
        assert any(v.rule == "enclosure" for v in report.violations)

    def test_sufficient_enclosure_passes(self, tmp_path: Path) -> None:
        gds = _gds(
            tmp_path,
            {
                (1, 0): [kdb.Box(0, 0, _um(4), _um(4))],
                (2, 0): [kdb.Box(_um(1), _um(1), _um(3), _um(3))],  # 1 um margin
            },
        )
        report = run_drc(self._pdk(), gds)
        assert not any(v.rule == "enclosure" for v in report.violations)

    def test_a_two_layer_rule_skips_when_one_layer_is_absent(self, tmp_path: Path) -> None:
        gds = _gds(tmp_path, {(1, 0): [kdb.Box(0, 0, _um(4), _um(4))]})
        report = run_drc(self._pdk(), gds)
        skipped = [c for c in report.checks if c.rule == "enclosure" and not c.ran]
        assert skipped and "no geometry" in (skipped[0].skip_reason or "")

    def test_a_rule_naming_an_unknown_layer_is_rejected_at_the_pdk(self) -> None:
        with pytest.raises(ValidationError, match="unknown layer"):
            _pdk(enclosures=[PDKEnclosure(inner="ghost", outer="metal", min_um=0.5)])


class TestAreaNotchAndSeparationRules:
    def test_minimum_area_is_caught_from_layer_width(self, tmp_path: Path) -> None:
        gds = _gds(tmp_path, {(1, 0): [kdb.Box(0, 0, _um(0.5), _um(0.5))]})
        report = run_drc(_pdk(), gds)
        violation = next(v for v in report.violations if v.rule == "min_area")
        assert violation.required_um == 1.0
        assert violation.unit == "um^2"

    def test_internal_notch_is_caught(self, tmp_path: Path) -> None:
        polygon = kdb.Polygon(
            [
                kdb.Point(0, 0),
                kdb.Point(_um(8), 0),
                kdb.Point(_um(8), _um(8)),
                kdb.Point(_um(5), _um(8)),
                kdb.Point(_um(5), _um(4.5)),
                kdb.Point(_um(3.5), _um(4.5)),
                kdb.Point(_um(3.5), _um(8)),
                kdb.Point(0, _um(8)),
            ]
        )
        layout = kdb.Layout()
        layout.dbu = 0.001
        top = layout.create_cell("TOP")
        top.shapes(layout.layer(1, 0)).insert(polygon)
        path = tmp_path / "notch.gds"
        layout.write(str(path))
        report = run_drc(_pdk(), path)
        assert any(v.rule == "notch" for v in report.violations)

    def test_inter_layer_separation_is_caught(self, tmp_path: Path) -> None:
        pdk = _pdk(
            layers=[
                PDKLayer(name="CPW_SIGNAL", purpose="metal", gds_layer=1, min_width_um=1.0, min_spacing_um=1.0),
                PDKLayer(name="CPW_GROUND", purpose="ground", gds_layer=2, min_width_um=1.0, min_spacing_um=1.0),
            ],
            separations=[
                PDKSeparation(
                    a="CPW_SIGNAL",
                    b="CPW_GROUND",
                    min_um=2.0,
                    rule_id="CPW.MIN_SIGNAL_GROUND_GAP",
                    description="CPW signal-ground gap must be at least 2 um.",
                )
            ],
        )
        gds = _gds(
            tmp_path,
            {
                (1, 0): [kdb.Box(0, 0, _um(5), _um(5))],
                (2, 0): [kdb.Box(_um(6), 0, _um(10), _um(5))],
            },
        )
        report = run_drc(pdk, gds)
        violation = next(v for v in report.violations if v.rule == "separation")
        assert violation.rule_id == "CPW.MIN_SIGNAL_GROUND_GAP"
        assert violation.required_um == 2.0


class TestTiledDensity:
    def _pdk(self, window: float | None = 10.0) -> PDK:
        return _pdk(
            layers=[
                PDKLayer(
                    name="metal", purpose="metal", gds_layer=1,
                    min_width_um=0.1, min_spacing_um=0.1,
                    min_density_fraction=0.2, max_density_fraction=0.8,
                )
            ],
            density_window_um=window,
        )

    def test_a_density_rule_without_a_window_is_rejected(self) -> None:
        """A whole-chip average is not a density check."""
        with pytest.raises(ValidationError, match="no density_window_um"):
            self._pdk(window=None)

    def test_a_locally_solid_region_fails_even_when_the_chip_average_passes(
        self, tmp_path: Path
    ) -> None:
        """Exactly what a whole-chip average would let through."""
        gds = _gds(
            tmp_path,
            {(1, 0): [kdb.Box(0, 0, _um(20), _um(40))]},  # solid half of a 40x40 area
        )
        # Chip-average fill is 0.5, inside [0.2, 0.8]. The solid window is 1.0.
        report = run_drc(self._pdk(), gds)
        assert any(v.rule == "density_tiled" for v in report.violations)

    def test_a_layout_smaller_than_the_window_is_skipped_not_passed(self, tmp_path: Path) -> None:
        gds = _gds(tmp_path, {(1, 0): [kdb.Box(0, 0, _um(2), _um(2))]})
        report = run_drc(self._pdk(window=50.0), gds)
        skipped = [c for c in report.checks if c.rule == "density_tiled" and not c.ran]
        assert skipped and "smaller than the" in (skipped[0].skip_reason or "")
        assert report.passed  # nothing fired...
        assert not any(c.rule == "density_tiled" and c.ran for c in report.checks)  # ...nothing ran


class TestJunctionRules:
    def _pdk(self) -> PDK:
        return _pdk(
            layers=[
                PDKLayer(name="jj", purpose="junction", gds_layer=5, min_width_um=0.05, min_spacing_um=0.05),
            ],
            junction_process=PDKJunctionProcess(
                target_jc_ua_per_um2=1.0, jc_sigma_pct=5.0, min_junction_area_um2=0.04
            ),
        )

    def test_an_undersized_junction_is_caught(self, tmp_path: Path) -> None:
        gds = _gds(tmp_path, {(5, 0): [kdb.Box(0, 0, _um(0.1), _um(0.1))]})  # 0.01 um^2
        report = run_drc(self._pdk(), gds)
        violation = next(v for v in report.violations if v.rule == "junction_min_area")
        assert violation.required_um == 0.04
        assert violation.count == 1

    def test_a_compliant_junction_passes(self, tmp_path: Path) -> None:
        gds = _gds(tmp_path, {(5, 0): [kdb.Box(0, 0, _um(0.3), _um(0.3))]})  # 0.09 um^2
        report = run_drc(self._pdk(), gds)
        assert not any(v.rule == "junction_min_area" for v in report.violations)

    def test_a_pdk_without_a_junction_process_runs_no_junction_rule(self, tmp_path: Path) -> None:
        gds = _gds(tmp_path, {(1, 0): [kdb.Box(0, 0, _um(5), _um(5))]})
        report = run_drc(_pdk(), gds)
        assert not any(c.rule == "junction_min_area" for c in report.checks)


class TestRunsetEmission:
    def test_the_runset_is_derived_from_the_same_pdk(self) -> None:
        pdk = _pdk(
            layers=[
                PDKLayer(name="metal", purpose="metal", gds_layer=1, min_width_um=1.0, min_spacing_um=2.0),
                PDKLayer(name="via", purpose="via", gds_layer=2, min_width_um=0.2, min_spacing_um=0.2),
            ],
            enclosures=[PDKEnclosure(inner="via", outer="metal", min_um=0.5)],
        )
        runset = to_lydrc(pdk)
        assert "metal = input(1, 0)" in runset
        assert "metal.width(1.0.um)" in runset
        assert "metal.space(2.0.um)" in runset
        assert "metal.with_area(nil, 1.0.um2)" in runset
        assert "metal.notch(2.0.um)" in runset
        assert "metal.enclosing(via, 0.5.um)" in runset

    def test_the_runset_names_what_it_does_not_check(self) -> None:
        runset = to_lydrc(_pdk())
        assert "does NOT check" in runset
        assert "antenna_ratio" in runset

    def test_the_runset_records_the_pdk_identity(self) -> None:
        runset = to_lydrc(_pdk())
        assert "test_pdk 0.1 (illustrative)" in runset


class TestReportSerialisation:
    def test_the_report_round_trips_to_a_dict(self, tmp_path: Path) -> None:
        gds = _gds(tmp_path, {(1, 0): [kdb.Box(0, 0, _um(0.4), _um(5))]})
        payload = run_drc(_pdk(), gds).to_dict()
        assert payload["schema"] == "textlayout.klayout-drc.v1"
        assert payload["passed"] is False
        assert payload["signoff_ready"] is False
        assert len(payload["gds_sha256"]) == 64
        assert payload["violations"][0]["rule"] == "min_width"

    def test_every_check_records_rule_and_pdk_identity(self, tmp_path: Path) -> None:
        gds = _gds(tmp_path, {(1, 0): [kdb.Box(0, 0, _um(5), _um(5))]})
        payload = run_drc(_pdk(), gds).to_dict()
        check = next(item for item in payload["checks"] if item["rule"] == "min_width")
        assert check["rule_id"] == "test_pdk.min_width.metal"
        assert check["description"] == "metal width must be at least 1.0 um."
        assert check["severity"] == "error"
        assert check["value"] == 1.0
        assert check["unit"] == "um"
        assert check["pdk_source"] == "synthetic, for tests"
        assert len(check["pdk_hash"]) == 64
        assert len(check["runset_hash"]) == 64

    def test_unimplemented_requested_rule_families_are_visible(self, tmp_path: Path) -> None:
        gds = _gds(tmp_path, {(1, 0): [kdb.Box(0, 0, _um(5), _um(5))]})
        unsupported = set(run_drc(_pdk(), gds).to_dict()["unsupported_rules"])
        assert {"acute_angle", "floating_conductor", "port_marker_placement"} <= unsupported

    def test_a_missing_gds_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            run_drc(_pdk(), tmp_path / "absent.gds")


class TestCommittedGoldenFixtures:
    def test_fixture_manifest_matches_gds_and_drc_results(self) -> None:
        manifest_path = REPO_ROOT / "tests" / "fixtures" / "klayout_drc" / "expectations.json"
        manifest = json.loads(manifest_path.read_text(encoding="ascii"))
        pdk = load_pdk(REPO_ROOT / manifest["pdk"])
        runset = to_lydrc(pdk)
        assert hashlib.sha256(runset.encode("utf-8")).hexdigest() == manifest["runset_hash"]

        for fixture in manifest["fixtures"]:
            gds = REPO_ROOT / fixture["path"]
            assert gds.is_file(), fixture["path"]
            assert _sha256(gds) == fixture["gds_hash"]
            report = run_drc(pdk, gds, top_cell=fixture["top_cell"])
            observed = {violation.rule_id for violation in report.violations}
            expected = set(fixture["expected_rule_ids"])
            assert expected <= observed, fixture["name"]
            unexpected = observed - expected
            assert len(unexpected) <= fixture["max_unexpected_violations"], fixture["name"]
            if not expected:
                assert report.passed, fixture["name"]
            else:
                assert len(report.violations) >= fixture["min_expected_violation_count"], fixture["name"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
