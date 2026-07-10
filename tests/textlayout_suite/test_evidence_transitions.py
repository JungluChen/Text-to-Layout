"""Every valid and invalid evidence state transition.

The invariant under test: **confidence may always be lost, and may only be
gained along the sanctioned path** (prepare inputs -> run solver -> compare to
target). A quantity that was skipped because the solver was missing must never
become PHYSICS_VERIFIED without a solver having run in between.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest

from textlayout.cli import main as cli_main
from textlayout.evidence import (
    ConfidenceClass,
    EvidenceError,
    EvidenceLedger,
    EvidenceStatus,
    QuantityEvidence,
    confidence_of,
    is_legal_transition,
    validate_transition,
)

QUANTITY = "capacitance"

#: The complete sanctioned promotion set, restated here independently of the
#: implementation so a change to the graph must be made deliberately in two
#: places rather than silently widened in one.
SANCTIONED_PROMOTIONS = {
    (EvidenceStatus.ANALYTICAL_ONLY, EvidenceStatus.SIMULATION_INPUT_PREPARED),
    (EvidenceStatus.FAILED, EvidenceStatus.SIMULATION_INPUT_PREPARED),
    (EvidenceStatus.SKIPPED_SOLVER_ABSENT, EvidenceStatus.SIMULATION_INPUT_PREPARED),
    (EvidenceStatus.SIMULATION_INVALID, EvidenceStatus.SIMULATION_INPUT_PREPARED),
    (EvidenceStatus.CONVERGENCE_FAILED, EvidenceStatus.SIMULATION_INPUT_PREPARED),
    (EvidenceStatus.FAILED, EvidenceStatus.ANALYTICAL_ONLY),
    (EvidenceStatus.SKIPPED_SOLVER_ABSENT, EvidenceStatus.ANALYTICAL_ONLY),
    (EvidenceStatus.SIMULATION_INVALID, EvidenceStatus.ANALYTICAL_ONLY),
    (EvidenceStatus.CONVERGENCE_FAILED, EvidenceStatus.ANALYTICAL_ONLY),
    (EvidenceStatus.SIMULATION_INPUT_PREPARED, EvidenceStatus.SIMULATION_EXECUTED),
    (EvidenceStatus.SIMULATION_EXECUTED, EvidenceStatus.PHYSICS_VERIFIED),
}


def _record(status: EvidenceStatus, out: Path) -> QuantityEvidence:
    """A minimal *valid* record for each status (the model rejects the rest)."""
    solver_kwargs = {
        "solver": "FasterCap 6.0.7",
        "parser": "textlayout.simulation.fastercap._parse",
        "command": "FasterCap -b idc.lst",
        "input_files": ["idc.lst"],
    }
    if status is EvidenceStatus.PHYSICS_VERIFIED:
        return QuantityEvidence(
            quantity=QUANTITY, status=status, target_value=0.6, target_unit="pF",
            extracted_value=0.598, extracted_unit="pF", error_percent=0.33,
            tolerance_percent=5.0, output_files=[str(out)], **solver_kwargs,
        )
    if status is EvidenceStatus.SIMULATION_EXECUTED:
        return QuantityEvidence(
            quantity=QUANTITY, status=status, target_value=0.6, target_unit="pF",
            extracted_value=0.9, extracted_unit="pF", error_percent=50.0,
            output_files=[str(out)], **solver_kwargs,
        )
    if status in (EvidenceStatus.SIMULATION_INVALID, EvidenceStatus.CONVERGENCE_FAILED):
        return QuantityEvidence(quantity=QUANTITY, status=status, solver="Palace")
    if status is EvidenceStatus.ANALYTICAL_ONLY:
        return QuantityEvidence(
            quantity=QUANTITY, status=status, analytical_value=0.61,
            analytical_model="conformal mapping",
        )
    # SIMULATION_INPUT_PREPARED, SKIPPED_SOLVER_ABSENT, FAILED
    return QuantityEvidence(quantity=QUANTITY, status=status)


@pytest.fixture
def out_file(tmp_path: Path) -> Path:
    path = tmp_path / "cap.txt"
    path.write_text("0.598\n", encoding="utf-8")
    return path


ALL_STATUSES = list(EvidenceStatus)


class TestConfidenceOrdering:
    def test_every_status_has_a_confidence_class(self) -> None:
        for status in ALL_STATUSES:
            assert isinstance(confidence_of(status), ConfidenceClass)

    def test_rejected_and_skipped_carry_no_confidence(self) -> None:
        for status in (
            EvidenceStatus.FAILED,
            EvidenceStatus.SKIPPED_SOLVER_ABSENT,
            EvidenceStatus.SIMULATION_INVALID,
            EvidenceStatus.CONVERGENCE_FAILED,
        ):
            assert confidence_of(status) is ConfidenceClass.NONE

    def test_verified_outranks_simulated_outranks_analytical(self) -> None:
        assert (
            confidence_of(EvidenceStatus.PHYSICS_VERIFIED)
            > confidence_of(EvidenceStatus.SIMULATION_EXECUTED)
            > confidence_of(EvidenceStatus.SIMULATION_INPUT_PREPARED)
            > confidence_of(EvidenceStatus.ANALYTICAL_ONLY)
            > confidence_of(EvidenceStatus.SKIPPED_SOLVER_ABSENT)
        )


class TestAllSixtyFourTransitions:
    """Sweep every (old, new) pair -- 8 statuses squared."""

    @pytest.mark.parametrize("old,new", list(itertools.product(ALL_STATUSES, ALL_STATUSES)))
    def test_transition_legality_matches_the_rule(
        self, old: EvidenceStatus, new: EvidenceStatus
    ) -> None:
        gains_confidence = confidence_of(new) > confidence_of(old)
        expected_legal = (not gains_confidence) or (old, new) in SANCTIONED_PROMOTIONS
        assert is_legal_transition(old, new) is expected_legal

        if expected_legal:
            validate_transition(old, new)  # must not raise
        else:
            with pytest.raises(EvidenceError, match="illegal confidence promotion"):
                validate_transition(old, new)

    def test_confidence_can_always_be_lost(self) -> None:
        """Any claim may be demoted at any time -- losing confidence is honest."""
        for old, new in itertools.product(ALL_STATUSES, ALL_STATUSES):
            if confidence_of(new) < confidence_of(old):
                validate_transition(old, new)  # must not raise


class TestIllegalPromotionsNamedExplicitly:
    """The specific jumps that would be dishonest, spelled out."""

    @pytest.mark.parametrize(
        "old",
        [
            EvidenceStatus.SKIPPED_SOLVER_ABSENT,
            EvidenceStatus.ANALYTICAL_ONLY,
            EvidenceStatus.SIMULATION_INPUT_PREPARED,
            EvidenceStatus.SIMULATION_INVALID,
            EvidenceStatus.CONVERGENCE_FAILED,
            EvidenceStatus.FAILED,
        ],
    )
    def test_nothing_reaches_physics_verified_except_via_simulation_executed(
        self, old: EvidenceStatus
    ) -> None:
        with pytest.raises(EvidenceError, match="illegal confidence promotion"):
            validate_transition(old, EvidenceStatus.PHYSICS_VERIFIED)
        # the one legal predecessor
        validate_transition(EvidenceStatus.SIMULATION_EXECUTED, EvidenceStatus.PHYSICS_VERIFIED)

    def test_analytical_cannot_become_a_solver_result_without_running_one(self) -> None:
        with pytest.raises(EvidenceError, match="illegal confidence promotion"):
            validate_transition(EvidenceStatus.ANALYTICAL_ONLY, EvidenceStatus.SIMULATION_EXECUTED)

    def test_a_rerun_may_invalidate_a_verified_claim(self) -> None:
        for demoted in (
            EvidenceStatus.SIMULATION_INVALID,
            EvidenceStatus.CONVERGENCE_FAILED,
            EvidenceStatus.SKIPPED_SOLVER_ABSENT,
            EvidenceStatus.FAILED,
        ):
            validate_transition(EvidenceStatus.PHYSICS_VERIFIED, demoted)


class TestEvidenceLedger:
    def test_records_the_sanctioned_path_end_to_end(self, out_file: Path) -> None:
        ledger = EvidenceLedger(QUANTITY)
        for status in (
            EvidenceStatus.ANALYTICAL_ONLY,
            EvidenceStatus.SIMULATION_INPUT_PREPARED,
            EvidenceStatus.SIMULATION_EXECUTED,
            EvidenceStatus.PHYSICS_VERIFIED,
        ):
            ledger.record(_record(status, out_file))
        assert len(ledger.history) == 4
        assert ledger.current is not None
        assert ledger.current.is_physics_verified
        assert ledger.current.confidence_class is ConfidenceClass.VERIFIED

    def test_ledger_refuses_the_skipped_to_verified_jump(self, out_file: Path) -> None:
        ledger = EvidenceLedger(QUANTITY)
        ledger.record(_record(EvidenceStatus.SKIPPED_SOLVER_ABSENT, out_file))
        with pytest.raises(EvidenceError, match="illegal confidence promotion"):
            ledger.record(_record(EvidenceStatus.PHYSICS_VERIFIED, out_file))
        # the ledger is unchanged by the rejected record
        assert len(ledger.history) == 1
        assert ledger.current is not None
        assert ledger.current.status is EvidenceStatus.SKIPPED_SOLVER_ABSENT

    def test_ledger_rejects_a_record_for_another_quantity(self, out_file: Path) -> None:
        ledger = EvidenceLedger("inductance")
        with pytest.raises(EvidenceError, match="refusing record"):
            ledger.record(_record(EvidenceStatus.FAILED, out_file))

    def test_a_hand_edited_ledger_does_not_load(self, out_file: Path) -> None:
        """from_dict re-validates: you cannot promote a claim by editing the file."""
        ledger = EvidenceLedger(QUANTITY)
        ledger.record(_record(EvidenceStatus.SKIPPED_SOLVER_ABSENT, out_file))
        payload = ledger.to_dict()
        # splice in a verified claim that no solver run justifies
        forged = _record(EvidenceStatus.PHYSICS_VERIFIED, out_file).model_dump(mode="json")
        payload["history"] = [*payload["history"], forged]  # type: ignore[misc]
        with pytest.raises(EvidenceError, match="illegal confidence promotion"):
            EvidenceLedger.from_dict(payload)

    def test_round_trip_preserves_a_legal_history(self, out_file: Path) -> None:
        ledger = EvidenceLedger(QUANTITY)
        ledger.record(_record(EvidenceStatus.SIMULATION_INPUT_PREPARED, out_file))
        ledger.record(_record(EvidenceStatus.SIMULATION_EXECUTED, out_file))
        restored = EvidenceLedger.from_dict(ledger.to_dict())
        assert [r.status for r in restored.history] == [r.status for r in ledger.history]
        assert restored.to_dict()["current_confidence"] == "SIMULATED"


class TestEvidenceCheckCLI:
    def _write(self, path: Path, ledger: EvidenceLedger) -> Path:
        path.write_text(json.dumps(ledger.to_dict(), indent=2), encoding="utf-8")
        return path

    def test_cli_accepts_a_legal_ledger(self, tmp_path: Path, out_file: Path, capsys) -> None:
        ledger = EvidenceLedger(QUANTITY)
        ledger.record(_record(EvidenceStatus.SIMULATION_INPUT_PREPARED, out_file))
        ledger.record(_record(EvidenceStatus.SIMULATION_EXECUTED, out_file))
        path = self._write(tmp_path / "ledger.json", ledger)

        assert cli_main(["evidence", "check", str(path)]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is True
        assert payload["current_status"] == "SIMULATION_EXECUTED"
        assert payload["current_confidence"] == "SIMULATED"
        assert payload["transitions_validated"] == 1

    def test_cli_exits_3_on_an_illegal_promotion(
        self, tmp_path: Path, out_file: Path, capsys
    ) -> None:
        ledger = EvidenceLedger(QUANTITY)
        ledger.record(_record(EvidenceStatus.SKIPPED_SOLVER_ABSENT, out_file))
        payload = ledger.to_dict()
        forged = _record(EvidenceStatus.PHYSICS_VERIFIED, out_file).model_dump(mode="json")
        payload["history"] = [*payload["history"], forged]  # type: ignore[misc]
        path = tmp_path / "forged.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        assert cli_main(["evidence", "check", str(path)]) == 3
        result = json.loads(capsys.readouterr().out)
        assert result["ok"] is False
        assert "illegal confidence promotion" in result["error"]
