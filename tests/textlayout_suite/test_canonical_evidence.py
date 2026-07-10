"""The canonical, content-addressed evidence record."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from textlayout.evidence import ConfidenceClass, EvidenceStatus
from textlayout.evidence.canonical import (
    ArtifactDependency,
    CanonicalEvidence,
    ConvergenceMetrics,
    MeasurementCorrelation,
    SanityCheck,
    SupersededClaim,
    compute_evidence_id,
    load_canonical,
    sha256_file,
    write_canonical,
)


def _converged() -> ConvergenceMetrics:
    return ConvergenceMetrics(
        method="fdtd_energy_decay", refinement_levels=1, delta_percent=0.4,
        threshold_percent=1.0, converged=True,
    )


def _base(out: Path, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "evidence_id": "abc123",
        "design_id": "02_cpw_50ohm",
        "design_hash": "d" * 64,
        "component": "CPW",
        "analysis_scope": "through_line",
        "target_quantity": "characteristic_impedance",
        "target_value": 50.0,
        "target_unit": "ohm",
        "extracted_quantity": "characteristic_impedance",
        "extracted_value": 49.7125,
        "extracted_unit": "ohm",
        "tolerance_percent": 5.0,
        "error_percent": -0.575,
        "status": EvidenceStatus.PHYSICS_VERIFIED,
        "solver_name": "openEMS",
        "solver_version": "0.0.36",
        "command": ["octave", "model.m"],
        "return_code": 0,
        "runtime_seconds": 1223.17,
        "output_file_hashes": {out.name: sha256_file(out)},
        "parser": "textlayout.simulation.runners.extract_cpw_from_touchstone",
        "parser_version": "1",
        "extraction_config": {"frequency_ghz": 6.0},
        "extraction_config_hash": "e" * 64,
        "convergence": _converged(),
        "timestamp": "2026-07-10T00:00:00+00:00",
        "provenance_gaps": ["solver_executable_hash_unrecorded"],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def out_file(tmp_path: Path) -> Path:
    path = tmp_path / "openems_result.s2p"
    path.write_text("# Hz S RI R 50\n1e9 0.1 0.0 0.9 0.0\n", encoding="utf-8")
    return path


class TestNonFiniteRejection:
    @pytest.mark.parametrize("field", ["extracted_value", "target_value", "error_percent"])
    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_no_numeric_field_may_be_non_finite(
        self, out_file: Path, field: str, bad: float
    ) -> None:
        with pytest.raises(ValidationError, match="must be finite"):
            CanonicalEvidence(**_base(out_file, **{field: bad}))  # type: ignore[arg-type]

    def test_convergence_metrics_reject_non_finite(self) -> None:
        with pytest.raises(ValidationError, match="must be finite"):
            ConvergenceMetrics(
                method="m", refinement_levels=1, delta_percent=float("nan"), converged=True
            )


class TestInvalidCarriesNoActiveValue:
    def test_simulation_invalid_rejects_an_extracted_value(self, out_file: Path) -> None:
        with pytest.raises(ValidationError, match="must not carry an active extracted_value"):
            CanonicalEvidence(
                **_base(
                    out_file,
                    status=EvidenceStatus.SIMULATION_INVALID,
                    invalidation_reason="all samples NaN",
                    convergence=None,
                    error_percent=None,
                )
            )

    def test_simulation_invalid_requires_a_reason(self, out_file: Path) -> None:
        with pytest.raises(ValidationError, match="requires an invalidation_reason"):
            CanonicalEvidence(
                **_base(
                    out_file,
                    status=EvidenceStatus.SIMULATION_INVALID,
                    extracted_value=None,
                    convergence=None,
                    error_percent=None,
                )
            )

    def test_withdrawn_number_lives_only_in_superseded(self, out_file: Path) -> None:
        record = CanonicalEvidence(
            **_base(
                out_file,
                status=EvidenceStatus.SIMULATION_INVALID,
                invalidation_reason="401/401 samples non-finite",
                extracted_value=None,
                convergence=None,
                error_percent=None,
                superseded=SupersededClaim(
                    status="RESONANCE_FREQUENCY_EXTRACTED",
                    extracted_value=3.0,
                    extracted_unit="GHz",
                    why_withdrawn="3.0 GHz is the first sweep point, not a resonance",
                ),
            )
        )
        assert record.extracted_value is None
        assert record.superseded is not None
        assert record.superseded.extracted_value == 3.0
        assert record.confidence_class is ConfidenceClass.NONE


class TestPhysicsVerifiedRequirements:
    def test_requires_convergence(self, out_file: Path) -> None:
        with pytest.raises(ValidationError, match="requires convergence metrics"):
            CanonicalEvidence(**_base(out_file, convergence=None))

    def test_requires_convergence_to_have_converged(self, out_file: Path) -> None:
        not_converged = ConvergenceMetrics(
            method="none_recorded", refinement_levels=1, converged=False
        )
        with pytest.raises(ValidationError, match="requires convergence metrics"):
            CanonicalEvidence(**_base(out_file, convergence=not_converged))

    def test_requires_output_hashes_not_merely_paths(self, out_file: Path) -> None:
        with pytest.raises(ValidationError, match="requires output_file_hashes"):
            CanonicalEvidence(**_base(out_file, output_file_hashes={}))

    def test_requires_an_extraction_config_hash(self, out_file: Path) -> None:
        with pytest.raises(ValidationError, match="requires extraction_config_hash"):
            CanonicalEvidence(**_base(out_file, extraction_config_hash=None))

    def test_requires_error_within_tolerance(self, out_file: Path) -> None:
        with pytest.raises(ValidationError, match=r"requires \|error\| <= tolerance"):
            CanonicalEvidence(**_base(out_file, error_percent=-50.0))

    def test_accepts_a_complete_record(self, out_file: Path) -> None:
        record = CanonicalEvidence(**_base(out_file))
        assert record.confidence_class is ConfidenceClass.VERIFIED


class TestProvenance:
    def test_solver_backed_record_must_declare_missing_executable_hash(
        self, out_file: Path
    ) -> None:
        with pytest.raises(ValidationError, match="must declare the gap in provenance_gaps"):
            CanonicalEvidence(**_base(out_file, provenance_gaps=[]))

    def test_container_digest_satisfies_solver_identity(self, out_file: Path) -> None:
        record = CanonicalEvidence(
            **_base(out_file, provenance_gaps=[], container_digest="sha256:" + "0" * 64)
        )
        assert record.container_digest is not None

    def test_analytical_only_cannot_name_a_solver(self, out_file: Path) -> None:
        with pytest.raises(ValidationError, match="must not name a solver"):
            CanonicalEvidence(
                **_base(
                    out_file,
                    status=EvidenceStatus.ANALYTICAL_ONLY,
                    extracted_value=None,
                    convergence=None,
                    error_percent=None,
                )
            )

    def test_confidence_class_is_derived_not_supplied(self, out_file: Path) -> None:
        """A record cannot claim more confidence than its status permits."""
        record = CanonicalEvidence(**_base(out_file))
        assert "confidence_class" not in CanonicalEvidence.model_fields
        assert record.to_dict()["confidence_class"] == "VERIFIED"
        # and a round-trip ignores any injected value
        payload = record.to_dict()
        payload["confidence_class"] = "NONE"
        assert CanonicalEvidence.model_validate(
            {k: v for k, v in payload.items() if k != "confidence_class"}
        ).confidence_class is ConfidenceClass.VERIFIED


class TestOutputHashVerification:
    def test_unmodified_output_verifies(self, tmp_path: Path, out_file: Path) -> None:
        record = CanonicalEvidence(**_base(out_file))
        assert record.verify_output_hashes(out_file.parent) == []

    def test_output_modified_after_evidence_is_detected(self, out_file: Path) -> None:
        """The failure a path-existence check cannot see."""
        record = CanonicalEvidence(**_base(out_file))
        out_file.write_text("# Hz S RI R 50\n1e9 0.2 0.0 0.8 0.0\n", encoding="utf-8")
        problems = record.verify_output_hashes(out_file.parent)
        assert len(problems) == 1
        assert "output changed after evidence was written" in problems[0]

    def test_missing_output_is_detected(self, out_file: Path) -> None:
        record = CanonicalEvidence(**_base(out_file))
        out_file.unlink()
        assert any("missing output file" in p for p in record.verify_output_hashes(out_file.parent))


class TestIdentityAndRoundTrip:
    def test_evidence_id_is_deterministic_and_config_sensitive(self) -> None:
        args = {"design_id": "02", "target_quantity": "z0", "output_file_hashes": {"a": "f" * 64}}
        first = compute_evidence_id(**args, extraction_config_hash="1" * 64)  # type: ignore[arg-type]
        again = compute_evidence_id(**args, extraction_config_hash="1" * 64)  # type: ignore[arg-type]
        other = compute_evidence_id(**args, extraction_config_hash="2" * 64)  # type: ignore[arg-type]
        assert first == again
        # the same parser over the same output under a different config is different evidence
        assert first != other

    def test_round_trip_through_disk(self, tmp_path: Path, out_file: Path) -> None:
        record = CanonicalEvidence(**_base(out_file))
        path = write_canonical(record, tmp_path / "evidence" / "canonical.json")
        restored = load_canonical(path)
        assert restored.status is record.status
        assert restored.extracted_value == record.extracted_value
        assert restored.output_file_hashes == record.output_file_hashes


class TestPhysicalSanityChecks:
    """A recorded sanity failure must veto every solver-backed status.

    This is the all-NaN Touchstone: the file existed, parsed, and yielded a
    float, so every *structural* check passed. Only a physical assertion --
    "the resonance is not sitting on the first sweep point" -- could catch it.
    """

    def test_a_failed_check_cannot_coexist_with_a_kept_value(self, out_file: Path) -> None:
        checks = [
            SanityCheck(name="s21_finite", passed=True),
            SanityCheck(
                name="resonance_not_at_sweep_edge",
                passed=False,
                detail="argmin over all-NaN magnitudes returned index 0",
            ),
        ]
        with pytest.raises(ValidationError, match="contradicts failed physical-sanity checks"):
            CanonicalEvidence(**_base(out_file, sanity_checks=checks))  # type: ignore[arg-type]

    def test_the_same_failed_check_is_fine_on_an_invalid_record(self, out_file: Path) -> None:
        record = CanonicalEvidence(
            **_base(  # type: ignore[arg-type]
                out_file,
                status=EvidenceStatus.SIMULATION_INVALID,
                extracted_value=None,
                error_percent=None,
                convergence=None,
                invalidation_reason="all 401 S-parameter samples were NaN",
                sanity_checks=[SanityCheck(name="s21_finite", passed=False)],
            )
        )
        assert record.confidence_class is ConfidenceClass.NONE
        assert record.extracted_value is None

    def test_passing_checks_do_not_block_verification(self, out_file: Path) -> None:
        record = CanonicalEvidence(
            **_base(  # type: ignore[arg-type]
                out_file, sanity_checks=[SanityCheck(name="s21_finite", passed=True)]
            )
        )
        assert record.status is EvidenceStatus.PHYSICS_VERIFIED


class TestMeasurementCorrelatedRecord:
    def _measurement(self, **overrides: object) -> MeasurementCorrelation:
        payload: dict[str, object] = {
            "measured_value": 49.9,
            "measured_unit": "ohm",
            "uncertainty": 0.3,
            "calibration_version": "cryo-cal-2026.02",
            "device_id": "lot7/w3/d12/dev4",
            "correlation_error_percent": 0.376,
        }
        payload.update(overrides)
        return MeasurementCorrelation(**payload)  # type: ignore[arg-type]

    def test_measurement_correlated_outranks_physics_verified(self, out_file: Path) -> None:
        record = CanonicalEvidence(
            **_base(  # type: ignore[arg-type]
                out_file,
                status=EvidenceStatus.MEASUREMENT_CORRELATED,
                measurement=self._measurement(),
            )
        )
        assert record.confidence_class is ConfidenceClass.MEASURED

    def test_measurement_correlated_requires_a_measurement_block(self, out_file: Path) -> None:
        with pytest.raises(ValidationError, match="requires a .measurement. block"):
            CanonicalEvidence(
                **_base(out_file, status=EvidenceStatus.MEASUREMENT_CORRELATED)  # type: ignore[arg-type]
            )

    def test_measurement_correlated_still_requires_convergence(self, out_file: Path) -> None:
        with pytest.raises(ValidationError, match="requires convergence metrics"):
            CanonicalEvidence(
                **_base(  # type: ignore[arg-type]
                    out_file,
                    status=EvidenceStatus.MEASUREMENT_CORRELATED,
                    measurement=self._measurement(),
                    convergence=None,
                )
            )

    def test_an_uncertainty_of_zero_is_not_a_measurement(self) -> None:
        with pytest.raises(ValidationError):
            self._measurement(uncertainty=0.0)

    def test_synthetic_measurements_are_marked_as_such(self) -> None:
        assert self._measurement().synthetic is False
        assert self._measurement(synthetic=True).synthetic is True


class TestNotFabricationReadyRecord:
    def test_requires_a_blocking_reason(self, out_file: Path) -> None:
        with pytest.raises(ValidationError, match="requires a blocking_reason"):
            CanonicalEvidence(
                **_base(  # type: ignore[arg-type]
                    out_file,
                    status=EvidenceStatus.NOT_FABRICATION_READY,
                    convergence=None,
                )
            )

    def test_a_good_number_on_an_unfabricable_design_claims_no_confidence(
        self, out_file: Path
    ) -> None:
        record = CanonicalEvidence(
            **_base(  # type: ignore[arg-type]
                out_file,
                status=EvidenceStatus.NOT_FABRICATION_READY,
                convergence=None,
                blocking_reason="junction overlap 40 nm < 60 nm process minimum",
            )
        )
        assert record.confidence_class is ConfidenceClass.NONE
        # The simulated number survives -- it is the *design* that is blocked.
        assert record.extracted_value == 49.7125


class TestQuantityEvidenceProjection:
    """The legacy model is a view of the canonical record, not a rival."""

    def test_projection_preserves_status_and_value(self, out_file: Path) -> None:
        record = CanonicalEvidence(**_base(out_file))  # type: ignore[arg-type]
        projected = record.to_quantity_evidence(root=out_file.parent)
        assert projected.status is record.status
        assert projected.quantity == record.target_quantity
        assert projected.extracted_value == record.extracted_value
        assert projected.is_physics_verified

    def test_projection_resolves_output_paths_the_legacy_model_demands(
        self, out_file: Path
    ) -> None:
        record = CanonicalEvidence(**_base(out_file))  # type: ignore[arg-type]
        projected = record.to_quantity_evidence(root=out_file.parent)
        assert projected.output_files == [str(out_file)]

    def test_projection_summarises_what_the_narrow_schema_cannot_hold(
        self, out_file: Path
    ) -> None:
        """Convergence, gaps and dependencies are surfaced, never silently dropped."""
        record = CanonicalEvidence(
            **_base(  # type: ignore[arg-type]
                out_file,
                depends_on=[ArtifactDependency(role="mesh", artifact="cpw.msh", sha256="a" * 64)],
                sanity_checks=[SanityCheck(name="s21_finite", passed=True)],
            )
        )
        notes = "\n".join(record.to_quantity_evidence(root=out_file.parent).notes)
        assert "convergence: fdtd_energy_decay" in notes
        assert "provenance gap: solver_executable_hash_unrecorded" in notes
        assert "depends on mesh: cpw.msh" in notes
        assert "sanity check s21_finite: pass" in notes

    def test_projection_carries_the_measurement_across(self, out_file: Path) -> None:
        record = CanonicalEvidence(
            **_base(  # type: ignore[arg-type]
                out_file,
                status=EvidenceStatus.MEASUREMENT_CORRELATED,
                measurement=MeasurementCorrelation(
                    measured_value=49.9, measured_unit="ohm", uncertainty=0.3,
                    calibration_version="cryo-cal-2026.02", device_id="lot7/w3/d12/dev4",
                ),
            )
        )
        projected = record.to_quantity_evidence(root=out_file.parent)
        assert projected.status is EvidenceStatus.MEASUREMENT_CORRELATED
        assert projected.measured_value == 49.9
        assert projected.calibration_version == "cryo-cal-2026.02"

    def test_a_blocked_design_projects_its_blocking_reason(self, out_file: Path) -> None:
        record = CanonicalEvidence(
            **_base(  # type: ignore[arg-type]
                out_file,
                status=EvidenceStatus.NOT_FABRICATION_READY,
                convergence=None,
                blocking_reason="junction overlap 40 nm < 60 nm process minimum",
            )
        )
        projected = record.to_quantity_evidence(root=out_file.parent)
        assert projected.blocking_reason is not None
        assert not projected.is_physics_verified
