"""The canonical, content-addressed evidence record."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from textlayout.evidence import ConfidenceClass, EvidenceStatus
from textlayout.evidence.canonical import (
    CanonicalEvidence,
    ConvergenceMetrics,
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
