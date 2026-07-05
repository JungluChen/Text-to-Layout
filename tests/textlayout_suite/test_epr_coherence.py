"""EPR participation + coherence estimation: math, honesty, CLI, determinism."""

from __future__ import annotations

import json
import math

import pytest

from textlayout.cli import main as cli_main
from textlayout.epr import (
    EPR_STATUS_ANALYTICAL,
    EPR_STATUS_SKIPPED,
    AnalyticalEPRBackend,
    ParticipationRecord,
    PyEPRBackend,
    estimate_coherence,
    illustrative_silicon_db,
    write_epr_report,
)
from textlayout.schemas.dsl import LayoutSpec

IDC_SPEC = {
    "component": "IDC",
    "technology": "generic_2metal",
    "target": {"capacitance_pf": 0.6, "frequency_ghz": 6.0},
    "parameters": {
        "finger_pairs": 22,
        "finger_width_um": 4,
        "gap_um": 2,
        "overlap_um": 250,
        "bus_width_um": 25,
        "metal_layer": "M1",
    },
    "rules": {"min_width_um": 2, "min_gap_um": 2},
}


def _spec(**overrides) -> LayoutSpec:
    data = dict(IDC_SPEC)
    data.update(overrides)
    return LayoutSpec.model_validate(data)


def _record(region: str, p: float, tan_delta: float) -> ParticipationRecord:
    return ParticipationRecord(
        region=region,
        material="test",
        p_electric=p,
        tan_delta=tan_delta,
        source="unit-test fixture",
        confidence=1.0,
        synthetic=True,
    )


class TestCoherenceMath:
    def test_q_total_is_inverse_participation_weighted_loss(self) -> None:
        records = [_record("a", 0.9, 1e-6), _record("b", 1e-3, 2e-3)]
        estimate = estimate_coherence(records, frequency_ghz=6.0)
        expected_inverse_q = 0.9 * 1e-6 + 1e-3 * 2e-3
        assert estimate.q_total == pytest.approx(1.0 / expected_inverse_q)

    def test_t1_equals_q_over_omega(self) -> None:
        records = [_record("a", 0.5, 1e-5)]
        frequency_ghz = 5.0
        estimate = estimate_coherence(records, frequency_ghz=frequency_ghz)
        omega = 2.0 * math.pi * frequency_ghz * 1e9
        assert estimate.t1_total_us == pytest.approx(estimate.q_total / omega * 1e6)

    def test_dominant_channel_and_loss_fractions(self) -> None:
        records = [_record("small", 1e-4, 1e-3), _record("big", 1e-3, 2e-3)]
        estimate = estimate_coherence(records, frequency_ghz=6.0)
        assert estimate.dominant_channel == "big"
        fractions = [row["loss_fraction"] for row in estimate.sensitivity_ranking]
        assert fractions == sorted(fractions, reverse=True)
        assert sum(float(f) for f in fractions) == pytest.approx(1.0)

    def test_zero_loss_is_refused(self) -> None:
        with pytest.raises(ValueError):
            estimate_coherence([], frequency_ghz=6.0)
        with pytest.raises(ValueError):
            estimate_coherence([_record("a", 0.5, 1e-5)], frequency_ghz=-1.0)


class TestAnalyticalBackend:
    def test_analytical_status_and_determinism(self) -> None:
        backend = AnalyticalEPRBackend()
        first = backend.analyze(_spec(), frequency_ghz=6.0)
        second = backend.analyze(_spec(), frequency_ghz=6.0)
        assert first.status == EPR_STATUS_ANALYTICAL
        assert first.participations == second.participations
        assert first.coherence is not None
        assert first.coherence.q_total == second.coherence.q_total

    def test_wider_gap_reduces_surface_participation(self) -> None:
        backend = AnalyticalEPRBackend()
        narrow_params = dict(IDC_SPEC["parameters"], gap_um=2)
        wide_params = dict(IDC_SPEC["parameters"], gap_um=10)
        narrow = backend.analyze(_spec(parameters=narrow_params), frequency_ghz=6.0)
        wide = backend.analyze(_spec(parameters=wide_params), frequency_ghz=6.0)

        def surface_p(result):
            return sum(p.p_electric for p in result.participations if p.region != "substrate")

        assert surface_p(wide) < surface_p(narrow)
        assert wide.coherence.q_total > narrow.coherence.q_total

    def test_participations_are_low_confidence_and_flagged_analytical(self) -> None:
        result = AnalyticalEPRBackend().analyze(_spec(), frequency_ghz=6.0)
        assert all(p.confidence <= 0.5 for p in result.participations)
        assert any("ANALYTICAL_ONLY" in note for note in result.notes)
        assert result.provenance["materials_db"] == illustrative_silicon_db().name

    def test_per_channel_q_limits_are_consistent(self) -> None:
        result = AnalyticalEPRBackend().analyze(_spec(), frequency_ghz=6.0)
        for p in result.participations:
            assert p.q_limit == pytest.approx(1.0 / (p.p_electric * p.tan_delta))

    def test_total_participation_never_exceeds_unity(self) -> None:
        tight_params = dict(IDC_SPEC["parameters"], gap_um=0.01)
        result = AnalyticalEPRBackend().analyze(_spec(parameters=tight_params), frequency_ghz=6.0)
        assert sum(p.p_electric for p in result.participations) <= 1.0


class TestPyEPRHonesty:
    def test_absent_pyepr_is_skipped_with_no_claims(self, monkeypatch) -> None:
        backend = PyEPRBackend()
        monkeypatch.setattr(PyEPRBackend, "available", lambda self: False)
        result = backend.analyze(_spec(), frequency_ghz=6.0)
        assert result.status == EPR_STATUS_SKIPPED
        assert result.participations == []
        assert result.coherence is None


class TestReportAndCLI:
    def test_write_epr_report_artifacts(self, tmp_path) -> None:
        result = AnalyticalEPRBackend().analyze(_spec(), frequency_ghz=6.0)
        files = write_epr_report(result, tmp_path)
        payload = json.loads((tmp_path / "epr_report.json").read_text(encoding="utf-8"))
        assert payload["status"] == EPR_STATUS_ANALYTICAL
        markdown = (tmp_path / "epr_report.md").read_text(encoding="utf-8")
        assert "does **not** imply coherence accuracy" in markdown
        assert set(files) == {"json", "markdown"}

    def test_cli_epr_command(self, tmp_path, capsys) -> None:
        spec_path = tmp_path / "idc.json"
        spec_path.write_text(json.dumps(IDC_SPEC), encoding="utf-8")
        code = cli_main(["epr", str(spec_path), "--out", str(tmp_path / "evidence")])
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == EPR_STATUS_ANALYTICAL
        assert payload["coherence"]["dominant_channel"]
        assert (tmp_path / "evidence" / "epr_report.md").is_file()

    def test_cli_verify_include_epr(self, tmp_path, capsys) -> None:
        spec_path = tmp_path / "idc.json"
        spec_path.write_text(json.dumps(IDC_SPEC), encoding="utf-8")
        code = cli_main(["verify", str(spec_path), "--include-epr"])
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["epr"]["status"] == EPR_STATUS_ANALYTICAL
        assert payload["epr"]["coherence"]["t1_total_us"] > 0
