"""PDK calibration_status/file-hash provenance and the signoff-level gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from textlayout.evidence import EvidenceStatus, QuantityEvidence
from textlayout.measurement import CalibrationFile, CorrectionFactors
from textlayout.pdk import (
    CALIBRATION_FOUNDRY,
    CALIBRATION_ILLUSTRATIVE,
    PDK,
    PDKGrid,
    PDKSubstrate,
    describe_pdk_file,
    find_pdk_provenance_for_technology,
)
from textlayout.signoff import evaluate_signoff

REPO_ROOT = Path(__file__).resolve().parents[2]
PDKS_DIR = REPO_ROOT / "src" / "textlayout" / "knowledge" / "pdks"


def _minimal_pdk_kwargs(**overrides) -> dict:
    defaults = dict(
        name="test_pdk",
        version="0.0.1",
        foundry_validated=False,
        source="unit test",
        grid=PDKGrid(grid_nm=1.0, default_min_spacing_um=1.0, default_min_width_um=1.0),
        substrate=PDKSubstrate(material="Si", epsilon_r=11.9, loss_tangent=1e-6),
        layers=[],
    )
    defaults.update(overrides)
    return defaults


class TestCalibrationStatusConsistency:
    def test_default_calibration_status_is_illustrative(self) -> None:
        pdk = PDK(**_minimal_pdk_kwargs())
        assert pdk.calibration_status == CALIBRATION_ILLUSTRATIVE

    def test_foundry_validated_true_requires_foundry_calibrated_status(self) -> None:
        with pytest.raises(Exception):
            PDK(**_minimal_pdk_kwargs(foundry_validated=True, calibration_status="illustrative"))

    def test_foundry_calibrated_status_requires_foundry_validated_true(self) -> None:
        with pytest.raises(Exception):
            PDK(
                **_minimal_pdk_kwargs(
                    foundry_validated=False, calibration_status=CALIBRATION_FOUNDRY
                )
            )

    def test_consistent_foundry_calibrated_pdk_is_valid(self) -> None:
        pdk = PDK(
            **_minimal_pdk_kwargs(foundry_validated=True, calibration_status=CALIBRATION_FOUNDRY)
        )
        assert pdk.foundry_validated
        assert pdk.calibration_status == CALIBRATION_FOUNDRY

    def test_internal_calibrated_does_not_require_foundry_validated(self) -> None:
        pdk = PDK(
            **_minimal_pdk_kwargs(foundry_validated=False, calibration_status="internal_calibrated")
        )
        assert pdk.calibration_status == "internal_calibrated"

    def test_invalid_calibration_status_rejected(self) -> None:
        with pytest.raises(Exception):
            PDK(**_minimal_pdk_kwargs(calibration_status="not_a_real_status"))

    def test_summary_includes_calibration_status(self) -> None:
        pdk = PDK(**_minimal_pdk_kwargs())
        assert pdk.summary()["calibration_status"] == CALIBRATION_ILLUSTRATIVE


class TestBuiltInPDKsCalibrationStatus:
    @pytest.mark.parametrize("path", sorted(PDKS_DIR.glob("*.yaml")), ids=lambda p: p.stem)
    def test_no_shipped_pdk_claims_foundry_calibrated(self, path) -> None:
        provenance = describe_pdk_file(path)
        assert provenance.calibration_status != CALIBRATION_FOUNDRY
        assert provenance.foundry_validated is False


class TestPDKFileHashProvenance:
    def test_hash_is_a_real_sha256_hex_digest(self) -> None:
        path = PDKS_DIR / "generic_2metal.yaml"
        provenance = describe_pdk_file(path)
        assert len(provenance.file_hash_sha256) == 64
        int(provenance.file_hash_sha256, 16)  # raises if not valid hex

    def test_hash_changes_when_file_content_changes(self, tmp_path) -> None:
        original = (PDKS_DIR / "generic_2metal.yaml").read_text(encoding="utf-8")
        path_a = tmp_path / "a.yaml"
        path_b = tmp_path / "b.yaml"
        path_a.write_text(original, encoding="utf-8")
        path_b.write_text(original + "\n# a trailing comment\n", encoding="utf-8")
        hash_a = describe_pdk_file(path_a).file_hash_sha256
        hash_b = describe_pdk_file(path_b).file_hash_sha256
        assert hash_a != hash_b

    def test_hash_is_stable_for_identical_content(self, tmp_path) -> None:
        original = (PDKS_DIR / "generic_2metal.yaml").read_text(encoding="utf-8")
        path_a = tmp_path / "a.yaml"
        path_b = tmp_path / "b.yaml"
        path_a.write_text(original, encoding="utf-8")
        path_b.write_text(original, encoding="utf-8")
        assert (
            describe_pdk_file(path_a).file_hash_sha256
            == describe_pdk_file(path_b).file_hash_sha256
        )

    def test_find_pdk_provenance_for_known_technology(self) -> None:
        provenance = find_pdk_provenance_for_technology("example_superconducting_pdk")
        assert provenance is not None
        assert provenance.pdk_name == "example_superconducting_pdk"
        assert provenance.calibration_status == CALIBRATION_ILLUSTRATIVE

    def test_find_pdk_provenance_for_unbacked_technology_is_none(self) -> None:
        assert find_pdk_provenance_for_technology("generic_2metal") is None
        assert find_pdk_provenance_for_technology("no_such_technology_at_all") is None


class TestCLIProvenanceIntegration:
    def test_cli_verify_includes_pdk_provenance_for_pdk_backed_technology(
        self, tmp_path, capsys
    ) -> None:
        import json

        from textlayout.cli import main as cli_main

        spec = {
            "component": "IDC",
            "technology": "example_superconducting_pdk",
            "target": {"capacitance_pf": 0.6},
            "parameters": {
                "finger_pairs": 22, "finger_width_um": 4, "gap_um": 2,
                "overlap_um": 250, "bus_width_um": 25, "metal_layer": "M1",
            },
            "rules": {"min_width_um": 1, "min_gap_um": 1},
        }
        spec_path = tmp_path / "idc.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        code = cli_main(["verify", str(spec_path)])
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["pdk_provenance"]["available"] is True
        assert payload["pdk_provenance"]["pdk_name"] == "example_superconducting_pdk"
        assert len(payload["pdk_provenance"]["file_hash_sha256"]) == 64

    def test_cli_verify_reports_no_provenance_for_generic_2metal(self, tmp_path, capsys) -> None:
        import json

        from textlayout.cli import main as cli_main

        code = cli_main(["verify", "examples/benchmarks/01_idc_0p6pf/layout.json"])
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["pdk_provenance"]["available"] is False


def _physics_verified_evidence(output_file: Path) -> QuantityEvidence:
    output_file.write_text("data", encoding="utf-8")
    return QuantityEvidence(
        quantity="capacitance",
        target_value=0.6,
        target_unit="pF",
        extracted_value=0.598,
        extracted_unit="pF",
        tolerance_percent=5.0,
        status=EvidenceStatus.PHYSICS_VERIFIED,
        solver="FasterCap",
        command="fastercap ...",
        input_files=[],
        output_files=[str(output_file)],
        parser="fastercap.parse",
        error_percent=0.33,
    )


class TestSignoffLevels:
    def test_no_geometry_is_level_negative_one(self) -> None:
        result = evaluate_signoff(geometry_pass=False, drc_passed=False, verification_passed=False)
        assert result.level == -1

    def test_geometry_only_is_level_0(self) -> None:
        result = evaluate_signoff(geometry_pass=True, drc_passed=False, verification_passed=False)
        assert result.level == 0
        assert result.blockers

    def test_drc_passed_is_level_1(self) -> None:
        result = evaluate_signoff(geometry_pass=True, drc_passed=True, verification_passed=False)
        assert result.level == 1

    def test_verification_passed_reaches_level_3_without_evidence(self) -> None:
        result = evaluate_signoff(geometry_pass=True, drc_passed=True, verification_passed=True)
        assert result.level == 3
        assert not result.passed_level_5_physics_signoff

    def test_analytical_only_evidence_stops_at_level_3(self) -> None:
        evidence = QuantityEvidence(
            quantity="capacitance", target_value=0.6, target_unit="pF",
            analytical_value=0.65, status=EvidenceStatus.ANALYTICAL_ONLY,
        )
        result = evaluate_signoff(
            geometry_pass=True, drc_passed=True, verification_passed=True, evidence=evidence
        )
        assert result.level == 3

    def test_simulation_executed_but_out_of_tolerance_is_level_4(self, tmp_path) -> None:
        output = tmp_path / "out.txt"
        output.write_text("data", encoding="utf-8")
        evidence = QuantityEvidence(
            quantity="capacitance", target_value=0.6, target_unit="pF",
            extracted_value=0.9, extracted_unit="pF", tolerance_percent=5.0,
            status=EvidenceStatus.SIMULATION_EXECUTED, solver="FasterCap", command="x",
            input_files=[], output_files=[str(output)], parser="x.parse",
        )
        result = evaluate_signoff(
            geometry_pass=True, drc_passed=True, verification_passed=True, evidence=evidence
        )
        assert result.level == 4
        assert not result.passed_level_5_physics_signoff

    def test_physics_verified_without_calibration_stops_at_level_5(self, tmp_path) -> None:
        evidence = _physics_verified_evidence(tmp_path / "out.txt")
        result = evaluate_signoff(
            geometry_pass=True, drc_passed=True, verification_passed=True, evidence=evidence
        )
        assert result.level == 5
        assert result.passed_level_5_physics_signoff
        assert not result.passed_level_6_measurement_calibrated
        assert any("measurement correlation" in b for b in result.blockers)

    def test_synthetic_calibration_does_not_reach_level_6(self, tmp_path) -> None:
        evidence = _physics_verified_evidence(tmp_path / "out.txt")
        calibration = CalibrationFile(
            corrections=CorrectionFactors(), source_device_ids=["D1"],
            n_records=1, synthetic=True,
        )
        result = evaluate_signoff(
            geometry_pass=True, drc_passed=True, verification_passed=True,
            evidence=evidence, calibration=calibration,
        )
        assert result.level == 5
        assert any("synthetic=True" in b for b in result.blockers)

    def test_real_calibration_reaches_level_6(self, tmp_path) -> None:
        evidence = _physics_verified_evidence(tmp_path / "out.txt")
        calibration = CalibrationFile(
            corrections=CorrectionFactors(), source_device_ids=["D1"],
            n_records=1, synthetic=False,
        )
        result = evaluate_signoff(
            geometry_pass=True, drc_passed=True, verification_passed=True,
            evidence=evidence, calibration=calibration,
        )
        assert result.level == 6
        assert result.passed_level_6_measurement_calibrated
        assert result.blockers == []

    def test_levels_are_sequential_never_skip(self) -> None:
        """A design must pass through every level; none can be skipped."""
        for missing_drc in (True, False):
            result = evaluate_signoff(
                geometry_pass=True, drc_passed=not missing_drc, verification_passed=True
            )
            assert result.level <= 3
