"""EPR participation + coherence estimation: math, honesty, CLI, determinism."""

from __future__ import annotations

import json
import math

import pytest

from pathlib import Path

from textlayout.cli import main as cli_main
from textlayout.epr import (
    EPR_SOLVER_BACKED_STATUSES,
    EPR_STATUS_ANALYTICAL,
    EPR_STATUS_FIELD_ENERGY_IMPORTED,
    EPR_STATUS_SKIPPED,
    AnalyticalEPRBackend,
    FieldEnergyImportBackend,
    ParticipationRecord,
    PyEPRBackend,
    estimate_coherence,
    illustrative_silicon_db,
    load_materials_db,
    write_epr_report,
)
from textlayout.schemas.dsl import LayoutSpec

REPO_ROOT = Path(__file__).resolve().parents[2]
FIELD_ENERGY_FIXTURE = (
    REPO_ROOT / "examples" / "epr_fixtures" / "field_energy_export_example.json"
)

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
        assert any("EPR_ANALYTICAL_ONLY" in note for note in result.notes)
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

    def test_cli_prompt_include_epr_appends_to_main_report(self, tmp_path, capsys) -> None:
        out_dir = tmp_path / "prompt_out"
        code = cli_main([
            "prompt", "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap",
            "--out", str(out_dir), "--no-solver", "--include-epr",
        ])
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["epr"]["status"] == EPR_STATUS_ANALYTICAL
        assert "epr_files" in payload
        assert (out_dir / "epr_report.json").is_file()
        report_text = (out_dir / "report.md").read_text(encoding="utf-8")
        assert "Coherence estimate" in report_text
        assert "Dominant loss channel" in report_text
        assert "Q_total" in report_text
        assert "does **not** imply coherence accuracy" in report_text

    def test_cli_prompt_without_include_epr_is_unchanged(self, tmp_path, capsys) -> None:
        """Backward compatibility: the flag must be strictly additive."""
        out_dir = tmp_path / "prompt_out_no_epr"
        code = cli_main([
            "prompt", "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap",
            "--out", str(out_dir), "--no-solver",
        ])
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert "epr" not in payload
        assert "epr_files" not in payload
        assert not (out_dir / "epr_report.json").is_file()
        report_text = (out_dir / "report.md").read_text(encoding="utf-8")
        assert "Coherence estimate" not in report_text


class TestFieldEnergyImportBackend:
    def test_committed_fixture_produces_field_energy_imported_status(self) -> None:
        backend = FieldEnergyImportBackend(FIELD_ENERGY_FIXTURE)
        assert backend.available()
        result = backend.analyze(_spec(), frequency_ghz=6.0)
        assert result.status == EPR_STATUS_FIELD_ENERGY_IMPORTED
        assert result.status in EPR_SOLVER_BACKED_STATUSES
        assert result.coherence is not None
        assert result.coherence.q_total > 0

    def test_participations_sum_to_expected_fractions(self) -> None:
        backend = FieldEnergyImportBackend(FIELD_ENERGY_FIXTURE)
        result = backend.analyze(_spec(), frequency_ghz=6.0)
        total = sum(p.p_electric for p in result.participations)
        assert total == pytest.approx(1.0, rel=1e-6)

    def test_higher_confidence_than_analytical_backend(self) -> None:
        """Real field-solved data should carry higher confidence than a scaling model."""
        analytical = AnalyticalEPRBackend().analyze(_spec(), frequency_ghz=6.0)
        imported = FieldEnergyImportBackend(FIELD_ENERGY_FIXTURE).analyze(
            _spec(), frequency_ghz=6.0
        )
        assert imported.participations[0].confidence > analytical.participations[0].confidence

    def test_missing_export_file_is_skipped_not_fabricated(self) -> None:
        backend = FieldEnergyImportBackend("does/not/exist.json")
        assert not backend.available()
        result = backend.analyze(_spec(), frequency_ghz=6.0)
        assert result.status == EPR_STATUS_SKIPPED
        assert result.participations == []
        assert result.coherence is None

    def test_empty_regions_raises(self, tmp_path) -> None:
        bad_fixture = tmp_path / "empty.json"
        bad_fixture.write_text(json.dumps({"schema": "x", "regions": []}), encoding="utf-8")
        backend = FieldEnergyImportBackend(bad_fixture)
        with pytest.raises(ValueError):
            backend.analyze(_spec(), frequency_ghz=6.0)


class TestMaterialsYamlLoading:
    def test_illustrative_db_loads_from_yaml(self) -> None:
        db = illustrative_silicon_db()
        assert db.name == "illustrative_si_surface_loss_v1"
        assert db.channel("substrate").calibration == "illustrative_literature_range"

    def test_load_materials_db_roundtrips_a_custom_file(self, tmp_path) -> None:
        import yaml

        payload = {
            "schema_version": "textlayout.loss-materials.v1",
            "name": "custom_test_db",
            "channels": {
                "substrate": {
                    "name": "substrate",
                    "material": "test material",
                    "tan_delta": 5e-5,
                    "source": "unit test",
                }
            },
        }
        path = tmp_path / "custom.yaml"
        path.write_text(yaml.safe_dump(payload), encoding="utf-8")
        db = load_materials_db(path)
        assert db.name == "custom_test_db"
        assert db.channel("substrate").tan_delta == 5e-5
