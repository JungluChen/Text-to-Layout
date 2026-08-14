"""Design-level signoff requires honest, independent solver agreement."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from textlayout.evidence import (
    CanonicalEvidence,
    ConvergenceMetrics,
    EvidenceStatus,
    SolverAgreementMember,
    SolverAgreementRecord,
    SolverOutputDigest,
    convert_value,
    solver_family,
)
from textlayout.measurement import CalibrationFile, CorrectionFactors
from textlayout.signoff import SIGNOFF_SCHEMA, evaluate_signoff

DESIGN_HASH = "a" * 64
OPENEMS_HASH = "b" * 64
PALACE_HASH = "c" * 64


def _evidence(
    *,
    evidence_id: str,
    solver: str,
    value: float,
    unit: str,
    output_path: str,
    output_hash: str,
    scope: str = "resonator_plus_coupler",
) -> CanonicalEvidence:
    return CanonicalEvidence(
        evidence_id=evidence_id,
        design_id="quarter_wave_6ghz",
        design_hash=DESIGN_HASH,
        component="CPWQuarterWaveResonator",
        analysis_scope=scope,
        target_quantity="resonance_frequency",
        target_value=6.0,
        target_unit="GHz",
        extracted_quantity="resonance_frequency",
        extracted_value=value,
        extracted_unit=unit,
        tolerance_percent=5.0,
        error_percent=0.9,
        status=EvidenceStatus.PHYSICS_VERIFIED,
        solver_name=solver,
        solver_version="test",
        solver_executable_sha256="d" * 64,
        output_file_hashes={output_path: output_hash},
        parser=f"{solver.casefold()}.parse",
        extraction_config_hash="e" * 64,
        convergence=ConvergenceMetrics(
            method="mesh_refinement",
            refinement_levels=3,
            delta_percent=0.8,
            threshold_percent=1.0,
            converged=True,
        ),
        timestamp="2026-08-14T00:00:00Z",
    )


def _member(record: CanonicalEvidence, *, size: int = 12) -> SolverAgreementMember:
    assert record.solver_name is not None
    assert record.extracted_value is not None
    assert record.extracted_unit is not None
    return SolverAgreementMember(
        evidence_id=record.evidence_id,
        solver_family=record.solver_name,
        extracted_value=record.extracted_value,
        extracted_unit=record.extracted_unit,
        outputs=tuple(
            SolverOutputDigest(path=path, sha256=digest, size_bytes=size)
            for path, digest in record.output_file_hashes.items()
        ),
    )


def _records_and_agreement() -> tuple[
    tuple[CanonicalEvidence, CanonicalEvidence], SolverAgreementRecord
]:
    openems = _evidence(
        evidence_id="openems-frequency",
        solver="openEMS",
        value=6.0,
        unit="GHz",
        output_path="openems.s2p",
        output_hash=OPENEMS_HASH,
    )
    palace = _evidence(
        evidence_id="palace-frequency",
        solver="Palace",
        value=6050.0,
        unit="MHz",
        output_path="palace.json",
        output_hash=PALACE_HASH,
    )
    records = (openems, palace)
    agreement = SolverAgreementRecord(
        design_hash=DESIGN_HASH,
        analysis_scope="resonator_plus_coupler",
        target_quantity="resonance_frequency",
        target_unit="GHz",
        members=tuple(_member(record) for record in records),
        tolerance_percent=5.0,
    )
    return records, agreement


def _evaluate(
    records: tuple[CanonicalEvidence, ...],
    agreement: SolverAgreementRecord,
    *,
    calibration: CalibrationFile | None = None,
):
    return evaluate_signoff(
        geometry_pass=True,
        drc_passed=True,
        verification_passed=True,
        solver_evidence=records,
        solver_agreement=agreement,
        calibration=calibration,
    )


def test_two_independent_solver_families_and_agreement_reach_level_5() -> None:
    records, agreement = _records_and_agreement()
    result = _evaluate(records, agreement)
    assert result.schema_version == SIGNOFF_SCHEMA == "textlayout.signoff.v2"
    assert result.level == 5
    assert result.passed_level_5_physics_signoff
    assert result.executed_solver_ids == ["openems-frequency", "palace-frequency"]
    assert result.executed_solver_evidence_ids == ["openems-frequency", "palace-frequency"]
    assert result.executed_solver_families == ["openems", "palace"]
    assert result.solver_agreement_status == "PASSED"
    assert result.solver_agreement_passed is True


def test_level_6_requires_level_5_plus_non_synthetic_calibration() -> None:
    records, agreement = _records_and_agreement()
    calibration = CalibrationFile(
        corrections=CorrectionFactors(),
        source_device_ids=["D1"],
        n_records=1,
        synthetic=False,
    )
    result = _evaluate(records, agreement, calibration=calibration)
    assert result.level == 6
    assert result.passed_level_6_measurement_calibrated
    assert result.blockers == []


def test_duplicate_solver_families_are_rejected() -> None:
    records, _ = _records_and_agreement()
    duplicate = records[0].model_copy(
        update={"evidence_id": "openems-second-run", "output_file_hashes": {"second.s2p": "f" * 64}}
    )
    with pytest.raises(ValidationError, match="independent solver families"):
        SolverAgreementRecord(
            design_hash=DESIGN_HASH,
            analysis_scope="resonator_plus_coupler",
            target_quantity="resonance_frequency",
            target_unit="GHz",
            members=(_member(records[0]), _member(duplicate)),
            tolerance_percent=5.0,
        )


def test_mismatched_analysis_scope_blocks_level_5() -> None:
    records, agreement = _records_and_agreement()
    mismatched = records[1].model_copy(update={"analysis_scope": "resonator_only"})
    result = _evaluate((records[0], mismatched), agreement)
    assert result.level == 4
    assert any("analysis scope mismatch" in blocker for blocker in result.blockers)


def test_missing_or_empty_output_digest_is_rejected() -> None:
    records, _ = _records_and_agreement()
    with pytest.raises(ValidationError):
        SolverAgreementMember(
            evidence_id=records[0].evidence_id,
            solver_family="openEMS",
            extracted_value=6.0,
            extracted_unit="GHz",
            outputs=(),
        )
    with pytest.raises(ValidationError):
        SolverOutputDigest(path="empty.s2p", sha256=OPENEMS_HASH, size_bytes=0)


def test_unit_mismatch_is_rejected() -> None:
    records, _ = _records_and_agreement()
    incompatible = _member(records[1]).model_copy(update={"extracted_unit": "pF"})
    with pytest.raises(ValidationError, match="cannot compare"):
        SolverAgreementRecord(
            design_hash=DESIGN_HASH,
            analysis_scope="resonator_plus_coupler",
            target_quantity="resonance_frequency",
            target_unit="GHz",
            members=(_member(records[0]), incompatible),
            tolerance_percent=5.0,
        )


def test_fabricated_passed_flag_is_forbidden() -> None:
    records, agreement = _records_and_agreement()
    payload = agreement.model_dump(mode="json")
    assert payload.pop("passed") is True
    payload.pop("relative_disagreement_percent")
    payload["passed"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SolverAgreementRecord.model_validate(payload)


def test_output_hash_mismatch_blocks_level_5() -> None:
    records, agreement = _records_and_agreement()
    bad_member = agreement.members[1].model_copy(
        update={
            "outputs": (
                SolverOutputDigest(path="palace.json", sha256="9" * 64, size_bytes=12),
            )
        }
    )
    bad_agreement = agreement.model_copy(update={"members": (agreement.members[0], bad_member)})
    result = _evaluate(records, bad_agreement)
    assert result.level == 4
    assert any("output hash mismatch" in blocker for blocker in result.blockers)


@pytest.mark.parametrize(
    ("value", "source", "target", "message"),
    [
        (float("nan"), "GHz", "GHz", "must be finite"),
        (1.0, "widgets", "GHz", "unsupported agreement unit"),
        (1.0, "GHz", "widgets", "unsupported agreement unit"),
        (1.0, "pF", "GHz", "cannot compare"),
    ],
)
def test_unit_conversion_fails_closed(value: float, source: str, target: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        convert_value(value, source, target)


def test_unit_and_solver_alias_normalization() -> None:
    assert convert_value(6000.0, "MHz", "GHz") == pytest.approx(6.0)
    assert convert_value(1.0, "µF", "nF") == pytest.approx(1000.0)
    assert convert_value(2.0, "kΩ", "ohm") == pytest.approx(2000.0)
    assert solver_family("Palace FEM 0.17.0") == "palace"
    assert solver_family("A New Solver") == "anewsolver"


def test_agreement_rejects_malformed_hashes_values_and_duplicate_members() -> None:
    records, agreement = _records_and_agreement()
    with pytest.raises(ValidationError, match="64-character hex"):
        SolverOutputDigest(path="x", sha256="not-a-hash", size_bytes=1)
    with pytest.raises(ValidationError, match="must be finite"):
        _member(records[0]).model_copy(update={"extracted_value": float("nan")}).model_validate(
            {
                **_member(records[0]).model_dump(mode="python"),
                "extracted_value": float("nan"),
            }
        )
    with pytest.raises(ValidationError, match="duplicate solver output paths"):
        SolverAgreementMember(
            **{
                **_member(records[0]).model_dump(mode="python"),
                "outputs": (_member(records[0]).outputs[0], _member(records[0]).outputs[0]),
            }
        )
    with pytest.raises(ValidationError, match="SHA-256"):
        SolverAgreementRecord(
            **{**agreement.model_dump(mode="python", exclude={"passed", "relative_disagreement_percent"}), "design_hash": "short"}
        )
    with pytest.raises(ValidationError, match="distinct canonical evidence IDs"):
        duplicate_id = agreement.members[1].model_copy(
            update={"evidence_id": agreement.members[0].evidence_id}
        )
        SolverAgreementRecord(
            design_hash=DESIGN_HASH,
            analysis_scope=agreement.analysis_scope,
            target_quantity=agreement.target_quantity,
            target_unit=agreement.target_unit,
            members=(agreement.members[0], duplicate_id),
            tolerance_percent=5.0,
        )


def test_zero_mean_and_out_of_tolerance_agreements_fail_honestly() -> None:
    records, agreement = _records_and_agreement()
    zero_members = (
        _member(records[0]).model_copy(update={"extracted_value": 0.0}),
        _member(records[1]).model_copy(update={"extracted_value": 0.0, "extracted_unit": "GHz"}),
    )
    zero = agreement.model_copy(update={"members": zero_members})
    assert zero.relative_disagreement_percent == 0.0
    assert zero.passed
    opposing = agreement.model_copy(
        update={
            "members": (
                zero_members[0].model_copy(update={"extracted_value": -1.0}),
                zero_members[1].model_copy(update={"extracted_value": 1.0}),
            )
        }
    )
    assert opposing.relative_disagreement_percent == pytest.approx(200.0)
    assert not opposing.passed
    assert any("exceeds tolerance" in problem for problem in opposing.validate_against(records))
    assert agreement.evidence_ids == ("openems-frequency", "palace-frequency")
    assert agreement.solver_families == ("openems", "palace")


def test_validate_against_reports_every_identity_mismatch() -> None:
    records, agreement = _records_and_agreement()
    altered = records[0].model_copy(
        update={
            "design_hash": "f" * 64,
            "target_quantity": "quality_factor",
            "target_unit": "pF",
            "status": EvidenceStatus.SIMULATION_EXECUTED,
            "solver_name": None,
            "extracted_value": 7.0,
            "extracted_unit": "MHz",
        }
    )
    problems = agreement.validate_against((altered,))
    expected_fragments = (
        "design hash mismatch",
        "target quantity mismatch",
        "target unit mismatch",
        "not quantity-level physics verified",
        "no solver identity",
        "extracted value mismatch",
        "extracted unit mismatch",
        "evidence ID not provided",
    )
    for fragment in expected_fragments:
        assert any(fragment in problem for problem in problems)


def test_solver_family_mismatch_is_reported() -> None:
    records, agreement = _records_and_agreement()
    wrong = agreement.members[0].model_copy(update={"solver_family": "elmer"})
    altered = agreement.model_copy(update={"members": (wrong, agreement.members[1])})
    problems = altered.validate_against(records)
    assert any("solver family mismatch" in problem for problem in problems)
