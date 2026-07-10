"""Cross-artifact evidence consistency.

The failure this suite exists to prevent: a resonator openEMS run produced an
all-NaN Touchstone file, its low-level result was corrected to
SIMULATION_INVALID, and eight derived artifacts kept publishing a successfully
extracted 3.0 GHz resonance.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from textlayout.evidence.consistency import (
    EVIDENCE_BLOCK,
    GENERATED_BEGIN,
    GENERATED_END,
    audit,
    check_showcase,
    classify_outcome,
    compatible,
    generated_block,
    iter_showcases,
)

ROOT = Path(__file__).resolve().parents[2]


class TestOutcomeCompatibility:
    """A solver outcome constrains, but does not equal, an evidence status."""

    def test_extracted_permits_executed_and_verified(self) -> None:
        for outcome in ("CAPACITANCE_EXTRACTED", "CHARACTERISTIC_IMPEDANCE_EXTRACTED"):
            assert classify_outcome(outcome) == "EXTRACTED"
            assert compatible(outcome, "SIMULATION_EXECUTED")
            assert compatible(outcome, "PHYSICS_VERIFIED")
            # extracting a number does not permit claiming nothing was extracted
            assert not compatible(outcome, "SIMULATION_INVALID")

    def test_simulation_invalid_permits_only_itself(self) -> None:
        """The exact rule that the resonator drift violated."""
        assert compatible("SIMULATION_INVALID", "SIMULATION_INVALID")
        for status in ("SIMULATION_EXECUTED", "PHYSICS_VERIFIED", "ANALYTICAL_ONLY"):
            assert not compatible("SIMULATION_INVALID", status)

    def test_input_prepared_never_permits_a_solver_result(self) -> None:
        assert compatible("EXTRACTION_INPUT_PREPARED", "ANALYTICAL_ONLY")
        assert compatible("EXTRACTION_INPUT_PREPARED", "SIMULATION_INPUT_PREPARED")
        assert not compatible("EXTRACTION_INPUT_PREPARED", "SIMULATION_EXECUTED")
        assert not compatible("EXTRACTION_INPUT_PREPARED", "PHYSICS_VERIFIED")


class TestGeneratedBlocks:
    def test_absent_markers_return_none(self) -> None:
        assert generated_block("# doc\n\nPHYSICS_VERIFIED everywhere\n") is None

    def test_only_block_contents_are_authoritative(self) -> None:
        text = (
            "Prose mentioning SIMULATION_EXECUTED sub-blocks.\n"
            + GENERATED_BEGIN.format(name=EVIDENCE_BLOCK)
            + "\nStatus: ANALYTICAL_ONLY\n"
            + GENERATED_END.format(name=EVIDENCE_BLOCK)
            + "\nMore prose about PHYSICS_VERIFIED elsewhere.\n"
        )
        block = generated_block(text)
        assert block is not None
        assert "ANALYTICAL_ONLY" in block
        assert "PHYSICS_VERIFIED" not in block


class TestDriftDetection:
    """Synthetic showcases: the checker must catch each drift class."""

    def _showcase(self, tmp_path: Path, *, sim_status: str, solver_status: str,
                  sim_value: float | None, solver_value: float | None) -> Path:
        d = tmp_path / "examples" / "showcase" / "99_synthetic"
        d.mkdir(parents=True)
        (d / "simulation.json").write_text(
            json.dumps({"status": sim_status, "extracted_value": sim_value}), encoding="utf-8"
        )
        (d / "openems_result.json").write_text(
            json.dumps(
                {
                    "status": solver_status,
                    "extracted_quantities": (
                        {} if solver_value is None else {"resonance_frequency_ghz": solver_value}
                    ),
                }
            ),
            encoding="utf-8",
        )
        return d

    def test_invalid_solver_result_cannot_back_an_executed_claim(self, tmp_path: Path) -> None:
        """Recreates the resonator failure mechanism exactly."""
        d = self._showcase(
            tmp_path,
            sim_status="SIMULATION_EXECUTED",
            solver_status="SIMULATION_INVALID",
            sim_value=3.0,
            solver_value=None,
        )
        report = check_showcase(d, tmp_path)
        assert not report.ok
        assert any("does not permit" in p for p in report.problems)

    def test_value_disagreement_is_reported(self, tmp_path: Path) -> None:
        d = self._showcase(
            tmp_path,
            sim_status="SIMULATION_EXECUTED",
            solver_status="RESONANCE_FREQUENCY_EXTRACTED",
            sim_value=3.0,
            solver_value=6.0,
        )
        report = check_showcase(d, tmp_path)
        assert any("extracted-value disagreement" in p for p in report.problems)

    def test_agreeing_artifacts_produce_no_status_or_value_problem(self, tmp_path: Path) -> None:
        d = self._showcase(
            tmp_path,
            sim_status="SIMULATION_EXECUTED",
            solver_status="RESONANCE_FREQUENCY_EXTRACTED",
            sim_value=6.0,
            solver_value=6.0,
        )
        report = check_showcase(d, tmp_path)
        assert not any("does not permit" in p for p in report.problems)
        assert not any("disagreement" in p for p in report.problems)


class TestRealRepositoryIsTraversedNotHardCoded:
    def test_every_showcase_directory_is_audited(self) -> None:
        found = {p.name for p in iter_showcases(ROOT)}
        listed = {
            entry["id"]
            for entry in json.loads(
                (ROOT / "examples" / "showcase" / "index.json").read_text(encoding="utf-8")
            )["examples"]
        }
        assert found == listed, "the auditor must traverse the directory, not a fixed list"

    def test_audit_returns_one_report_per_showcase(self) -> None:
        reports = audit(ROOT)
        assert len(reports) == len(iter_showcases(ROOT))
        assert all(r.showcase_id for r in reports)


@pytest.mark.xfail(
    strict=True,
    reason="Phase 1 baseline: 0/6 showcases are consistent. Every status is "
    "hand-maintained, no canonical evidence exists, and the resonator's "
    "SIMULATION_INVALID result is contradicted by 8 derived artifacts. "
    "See docs/evidence_consistency_baseline.md. strict=True so this flips to a "
    "hard failure the moment the repository becomes consistent.",
)
@pytest.mark.parametrize("showcase", [p.name for p in iter_showcases(ROOT)])
def test_every_showcase_is_consistent(showcase: str) -> None:
    """The release gate: no showcase may contradict itself or its canonical record."""
    reports = {r.showcase_id: r for r in audit(ROOT)}
    report = reports[showcase]
    assert report.ok, "\n".join(f"  - {p}" for p in report.problems)
