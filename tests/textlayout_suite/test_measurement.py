"""Measurement correlation loop: residuals, correction-factor fitting, CLI."""

from __future__ import annotations

import json

import pytest

from textlayout.cli import main as cli_main
from textlayout.measurement import (
    CalibrationFile,
    MeasurementRecord,
    SimulatedPrediction,
    build_calibration,
    build_comparison_summary,
    compare_all,
    compare_pair,
    fit_correction_factors,
    load_calibration,
    pair_by_design_hash,
    write_calibration,
    write_calibration_report,
    write_comparison_report,
)


def _pred(**overrides) -> SimulatedPrediction:
    defaults = dict(
        design_hash="idc_0p6pf_v1",
        predicted_frequency_ghz=6.0,
        predicted_capacitance_pf=0.6,
        source="FasterCap 6.0.7",
    )
    defaults.update(overrides)
    return SimulatedPrediction(**defaults)


def _meas(**overrides) -> MeasurementRecord:
    defaults = dict(
        device_id="D001",
        wafer_id="W17",
        design_hash="idc_0p6pf_v1",
        measured_frequency_ghz=6.05,
        measured_capacitance_pf=0.615,
        temperature_k=0.015,
        cooldown_id="CD-2026-01",
    )
    defaults.update(overrides)
    return MeasurementRecord(**defaults)


class TestResidualComparison:
    def test_compare_pair_computes_both_quantities(self) -> None:
        residuals = compare_pair(_pred(), _meas())
        by_quantity = {r.quantity: r for r in residuals}
        assert set(by_quantity) == {"frequency_ghz", "capacitance_pf"}
        freq = by_quantity["frequency_ghz"]
        assert freq.simulated_value == 6.0
        assert freq.measured_value == 6.05
        assert freq.error_absolute == pytest.approx(0.05)
        assert freq.error_percent == pytest.approx(0.05 / 6.0 * 100.0)

    def test_only_shared_quantities_are_compared(self) -> None:
        pred = _pred(predicted_q=15000.0)  # no predicted_inductance_nh
        meas = _meas(measured_inductance_nh=3.1)  # no measured_q
        residuals = compare_pair(pred, meas)
        quantities = {r.quantity for r in residuals}
        assert "inductance_nh" not in quantities
        assert "q" not in quantities  # neither side has BOTH

    def test_mismatched_design_hash_raises(self) -> None:
        with pytest.raises(ValueError):
            compare_pair(_pred(design_hash="a"), _meas(design_hash="b"))

    def test_compare_all_aggregates_multiple_pairs(self) -> None:
        pairs = [
            (_pred(), _meas()),
            (
                _pred(design_hash="x", predicted_frequency_ghz=5.0),
                _meas(device_id="D002", design_hash="x", measured_frequency_ghz=5.1),
            ),
        ]
        residuals = compare_all(pairs)
        assert {r.device_id for r in residuals} == {"D001", "D002"}


class TestCorrectionFactorFit:
    def test_single_pair_capacitance_scale(self) -> None:
        corrections = fit_correction_factors([(_pred(), _meas())])
        assert corrections.capacitance_scale == pytest.approx(0.615 / 0.6)
        assert corrections.n_capacitance_pairs == 1

    def test_jc_scale_uses_frequency_ratio_squared_over_capacitance_scale(self) -> None:
        pred = _pred(predicted_frequency_ghz=6.0, predicted_capacitance_pf=0.6)
        meas = _meas(measured_frequency_ghz=6.06, measured_capacitance_pf=0.6)  # no C shift
        corrections = fit_correction_factors([(pred, meas)])
        expected = (6.06 / 6.0) ** 2 / 1.0
        assert corrections.jc_scale == pytest.approx(expected)

    def test_jc_scale_defaults_capacitance_to_unity_without_c_measurement(self) -> None:
        pred = _pred(predicted_capacitance_pf=None, predicted_frequency_ghz=6.0)
        meas = _meas(measured_capacitance_pf=None, measured_frequency_ghz=6.06)
        corrections = fit_correction_factors([(pred, meas)])
        expected = (6.06 / 6.0) ** 2  # / 1.0 implicit
        assert corrections.jc_scale == pytest.approx(expected)

    def test_loss_tangent_scale_from_q_ratio(self) -> None:
        pred = _pred(predicted_q=15000.0)
        meas = _meas(measured_q=9500.0)
        corrections = fit_correction_factors([(pred, meas)])
        assert corrections.loss_tangent_scale == pytest.approx(15000.0 / 9500.0)

    def test_missing_quantity_excluded_not_zero(self) -> None:
        pred = _pred(predicted_capacitance_pf=None)
        meas = _meas(measured_capacitance_pf=None)
        corrections = fit_correction_factors([(pred, meas)])
        assert corrections.capacitance_scale is None
        assert corrections.n_capacitance_pairs == 0

    def test_sigma_pct_none_for_single_device(self) -> None:
        corrections = fit_correction_factors([(_pred(), _meas())])
        assert corrections.jc_scale_sigma_pct is None  # need >= 2 devices for a spread

    def test_sigma_pct_computed_for_multiple_devices(self) -> None:
        pairs = [
            (
                _pred(design_hash=f"d{i}", predicted_frequency_ghz=6.0),
                _meas(
                    device_id=f"D{i}",
                    design_hash=f"d{i}",
                    measured_frequency_ghz=6.0 + 0.01 * i,
                    measured_capacitance_pf=None,
                ),
            )
            for i in range(4)
        ]
        pairs = [(p.model_copy(update={"predicted_capacitance_pf": None}), m) for p, m in pairs]
        corrections = fit_correction_factors(pairs)
        assert corrections.jc_scale_sigma_pct is not None
        assert corrections.jc_scale_sigma_pct >= 0.0

    def test_empty_pairs_rejected(self) -> None:
        with pytest.raises(ValueError):
            fit_correction_factors([])

    def test_mismatched_design_hash_pair_rejected(self) -> None:
        with pytest.raises(ValueError):
            fit_correction_factors([(_pred(design_hash="a"), _meas(design_hash="b"))])


class TestPairingAndCalibration:
    def test_pair_by_design_hash_matches_correctly(self) -> None:
        predictions = [_pred(), _pred(design_hash="other", predicted_frequency_ghz=5.0)]
        measurements = [_meas()]  # only matches the first prediction
        pairs = pair_by_design_hash(predictions, measurements)
        assert len(pairs) == 1
        assert pairs[0][0].design_hash == "idc_0p6pf_v1"

    def test_unmatched_measurement_silently_excluded(self) -> None:
        predictions = [_pred()]
        measurements = [_meas(design_hash="no_such_design")]
        pairs = pair_by_design_hash(predictions, measurements)
        assert pairs == []

    def test_duplicate_design_hash_in_predictions_rejected(self) -> None:
        predictions = [_pred(), _pred()]
        with pytest.raises(ValueError):
            pair_by_design_hash(predictions, [_meas()])

    def test_duplicate_device_id_in_measurements_rejected(self) -> None:
        with pytest.raises(ValueError):
            pair_by_design_hash([_pred()], [_meas(), _meas()])

    def test_build_calibration_marks_synthetic_by_default(self) -> None:
        calibration = build_calibration([_pred()], [_meas()])
        assert calibration.synthetic is True
        assert calibration.n_records == 1
        assert calibration.source_device_ids == ["D001"]

    def test_build_calibration_production_flag(self) -> None:
        calibration = build_calibration([_pred()], [_meas()], synthetic=False)
        assert calibration.synthetic is False
        assert calibration.notes == []

    def test_build_calibration_no_overlap_rejected(self) -> None:
        with pytest.raises(ValueError):
            build_calibration([_pred(design_hash="a")], [_meas(design_hash="b")])

    def test_calibration_yaml_roundtrip(self, tmp_path) -> None:
        calibration = build_calibration([_pred()], [_meas()])
        path = write_calibration(calibration, tmp_path / "calibration.yaml")
        loaded = load_calibration(path)
        assert loaded == calibration


class TestReportsAndCLI:
    def test_write_comparison_report(self, tmp_path) -> None:
        residuals = compare_pair(_pred(), _meas())
        files = write_comparison_report(residuals, tmp_path)
        assert set(files) == {"json", "markdown"}
        payload = json.loads((tmp_path / "measurement_comparison.json").read_text(encoding="utf-8"))
        assert len(payload) == 2

    def test_write_calibration_report(self, tmp_path) -> None:
        calibration = build_calibration([_pred()], [_meas()])
        files = write_calibration_report(calibration, tmp_path)
        markdown = (tmp_path / "calibration_report.md").read_text(encoding="utf-8")
        assert "SYNTHETIC" in markdown
        assert set(files) == {"markdown"}

    def test_cli_measurement_compare(self, tmp_path, capsys) -> None:
        pred_path = tmp_path / "predictions.json"
        meas_path = tmp_path / "measurements.json"
        pred_path.write_text(json.dumps([_pred().model_dump(mode="json")]), encoding="utf-8")
        meas_path.write_text(json.dumps([_meas().model_dump(mode="json")]), encoding="utf-8")
        code = cli_main(
            [
                "measurement",
                "compare",
                "--predicted",
                str(pred_path),
                "--measured",
                str(meas_path),
                "--out",
                str(tmp_path / "evidence"),
            ]
        )
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert len(payload["residuals"]) == 2
        assert (tmp_path / "evidence" / "measurement_comparison.md").is_file()

    def test_cli_measurement_calibrate(self, tmp_path, capsys) -> None:
        pred_path = tmp_path / "predictions.json"
        meas_path = tmp_path / "measurements.json"
        pred_path.write_text(json.dumps([_pred().model_dump(mode="json")]), encoding="utf-8")
        meas_path.write_text(json.dumps([_meas().model_dump(mode="json")]), encoding="utf-8")
        code = cli_main(
            [
                "measurement",
                "calibrate",
                "--predicted",
                str(pred_path),
                "--measured",
                str(meas_path),
                "--out",
                str(tmp_path / "evidence"),
            ]
        )
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        # legacy top-level calibration keys stay at the top level (back-compat)
        assert payload["synthetic"] is True
        assert "corrections" in payload
        # the overlay is additive
        assert payload["overlay"]["calibration_status"] == "SYNTHETIC_CALIBRATION_ONLY"
        assert (tmp_path / "evidence" / "calibration.yaml").is_file()
        assert (tmp_path / "evidence" / "calibrated_pdk_overlay.yaml").is_file()

    def test_cli_measurement_calibrate_production_flag(self, tmp_path, capsys) -> None:
        """--production on genuinely non-synthetic records yields synthetic=False."""
        pred_path = tmp_path / "predictions.json"
        meas_path = tmp_path / "measurements.json"
        real = _meas(synthetic=False, measurement_source="fridge-A VNA")
        pred_path.write_text(json.dumps([_pred().model_dump(mode="json")]), encoding="utf-8")
        meas_path.write_text(json.dumps([real.model_dump(mode="json")]), encoding="utf-8")
        code = cli_main(
            [
                "measurement",
                "calibrate",
                "--predicted",
                str(pred_path),
                "--measured",
                str(meas_path),
                "--production",
            ]
        )
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["synthetic"] is False
        assert payload["overlay"]["is_synthetic"] is False
        assert payload["overlay"]["calibration_status"] == "MEASUREMENT_CALIBRATED"

    def test_cli_measurement_calibrate_production_refuses_synthetic(self, tmp_path, capsys) -> None:
        """--production must NOT promote fixture data: synthetic inputs are refused.

        Guards the honesty invariant that the flag is an assertion about the
        *data*, not an override of it.
        """
        pred_path = tmp_path / "predictions.json"
        meas_path = tmp_path / "measurements.json"
        pred_path.write_text(json.dumps([_pred().model_dump(mode="json")]), encoding="utf-8")
        meas_path.write_text(json.dumps([_meas().model_dump(mode="json")]), encoding="utf-8")
        code = cli_main(
            [
                "measurement",
                "calibrate",
                "--predicted",
                str(pred_path),
                "--measured",
                str(meas_path),
                "--production",
            ]
        )
        assert code == 2
        assert "refusing" in json.loads(capsys.readouterr().out)["error"]


class TestComparisonCoverage:
    """Coverage must never look complete when most devices went unmatched."""

    def test_coverage_is_asymmetric_between_predictions_and_measurements(self) -> None:
        """40 predicted / 2 measured is 5% coverage, not 100%."""
        summary = build_comparison_summary(
            [],
            n_predictions=40,
            n_measurements=2,
            n_matched=2,
            any_synthetic=False,
            pdk_names=[],
        )
        assert summary["coverage_pct"] == pytest.approx(5.0)
        assert summary["n_unmatched_predictions"] == 38
        assert summary["n_unmatched_measurements"] == 0
        assert summary["comparison_status"] == "PARTIAL_MEASUREMENT_MATCH"

        # the mirror image is a *different* evidence situation
        mirrored = build_comparison_summary(
            [],
            n_predictions=2,
            n_measurements=40,
            n_matched=2,
            any_synthetic=False,
            pdk_names=[],
        )
        assert mirrored["n_unmatched_predictions"] == 0
        assert mirrored["n_unmatched_measurements"] == 38
        # the legacy scalar cannot tell these two apart -- which is why it is not enough
        assert summary["n_unmatched"] == mirrored["n_unmatched"]

    def test_no_devices_is_insufficient_not_full_coverage(self) -> None:
        summary = build_comparison_summary(
            [], n_predictions=0, n_measurements=0, n_matched=0, any_synthetic=False, pdk_names=[]
        )
        assert summary["coverage_pct"] == 0.0
        assert summary["comparison_status"] == "INSUFFICIENT_MEASUREMENT_DATA"
        assert summary["quantities_compared"] == []

    def test_full_match_is_full_coverage(self) -> None:
        pairs = pair_by_design_hash([_pred()], [_meas()])
        residuals = compare_all(pairs)
        summary = build_comparison_summary(
            residuals,
            n_predictions=1,
            n_measurements=1,
            n_matched=1,
            any_synthetic=True,
            pdk_names=["illustrative"],
        )
        assert summary["coverage_pct"] == pytest.approx(100.0)
        assert summary["comparison_status"] == "MEASUREMENT_COMPARED"
        assert "SYNTHETIC_MEASUREMENT" in summary["labels"]
        assert summary["quantities_compared"]  # residuals produced real quantities


class TestSyntheticFixtures:
    """The committed examples/measurement_fixtures/ files must stay valid."""

    def test_committed_fixtures_load_and_calibrate(self) -> None:
        import json as _json
        from pathlib import Path

        root = Path(__file__).resolve().parents[2] / "examples" / "measurement_fixtures"
        predictions = [
            SimulatedPrediction.model_validate(item)
            for item in _json.loads((root / "predictions.json").read_text(encoding="utf-8"))
        ]
        measurements = [
            MeasurementRecord.model_validate(item)
            for item in _json.loads((root / "measurements.json").read_text(encoding="utf-8"))
        ]
        calibration = build_calibration(predictions, measurements)
        assert isinstance(calibration, CalibrationFile)
        assert calibration.n_records == 3
