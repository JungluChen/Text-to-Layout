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

from textlayout.evidence import EvidenceStatus
from textlayout.evidence.consistency import (
    EVIDENCE_BLOCK,
    GENERATED_BEGIN,
    GENERATED_END,
    _first_status_token,
    _STATUS_TOKENS,
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


@pytest.mark.parametrize("showcase", [p.name for p in iter_showcases(ROOT)])
def test_every_showcase_is_consistent(showcase: str) -> None:
    """The release gate: no showcase may contradict itself or its canonical record."""
    reports = {r.showcase_id: r for r in audit(ROOT)}
    report = reports[showcase]
    assert report.ok, "\n".join(f"  - {p}" for p in report.problems)


class TestSolverOutputSanityGates:
    """The extraction gates that the resonator's data must trip."""

    def _write_s2p(self, path: Path, rows: list[str]) -> Path:
        path.write_text("# Hz S RI R 50\n" + "\n".join(rows) + "\n", encoding="utf-8")
        return path

    def test_all_nan_data_is_rejected_not_extremised(self, tmp_path: Path) -> None:
        """Recreates the resonator failure mechanism from raw data."""
        from textlayout.simulation.runners import extract_resonance_metrics_from_touchstone

        nan_row = " ".join(["NaN 0.0"] * 4)
        path = self._write_s2p(
            tmp_path / "all_nan.s2p",
            [f"{3e9 + i * 1e7:.6e} {nan_row}" for i in range(20)],
        )
        with pytest.raises(ValueError, match="non-finite"):
            extract_resonance_metrics_from_touchstone(path)

    def test_partially_finite_data_is_rejected(self, tmp_path: Path) -> None:
        """One NaN sample poisons the extremum search; the parser must refuse."""
        from textlayout.simulation.runners import extract_resonance_metrics_from_touchstone

        rows = [f"{3e9 + i * 1e7:.6e} 0.1 0.0 0.9 0.0 0.9 0.0 0.1 0.0" for i in range(20)]
        rows[7] = f"{3e9 + 7e7:.6e} NaN 0.0 NaN 0.0 NaN 0.0 NaN 0.0"
        path = self._write_s2p(tmp_path / "partial.s2p", rows)
        with pytest.raises(ValueError, match="non-finite"):
            extract_resonance_metrics_from_touchstone(path)

    def test_monotonic_data_does_not_yield_a_sweep_edge_resonance(self, tmp_path: Path) -> None:
        """Monotonic S21 has its extremum at an edge: that is NO resonance in band."""
        from textlayout.simulation.sparameters import find_resonance_frequency

        rows = [
            f"{3e9 + i * 1e7:.6e} 0.01 0.0 {0.9 - i * 0.01:.4f} 0.0 "
            f"{0.9 - i * 0.01:.4f} 0.0 0.01 0.0"
            for i in range(20)
        ]
        path = self._write_s2p(tmp_path / "monotonic.s2p", rows)
        with pytest.raises(ValueError):
            find_resonance_frequency(path)

    def test_a_real_interior_dip_is_accepted(self, tmp_path: Path) -> None:
        """The guard must not reject genuine resonances."""
        from textlayout.simulation.sparameters import find_resonance_frequency

        rows = []
        for i in range(21):
            s21 = 0.9 if i != 10 else 0.05
            rows.append(f"{3e9 + i * 1e7:.6e} 0.01 0.0 {s21:.4f} 0.0 {s21:.4f} 0.0 0.01 0.0")
        path = self._write_s2p(tmp_path / "dip.s2p", rows)
        assert find_resonance_frequency(path) == pytest.approx(3e9 + 10 * 1e7)


class TestCanonicalRecordsMatchCommittedOutputs:
    """`build_canonical` must re-derive exactly what is committed."""

    def test_every_canonical_record_is_reproducible(self) -> None:
        from textlayout.evidence.build import RECIPES, build_canonical
        from textlayout.evidence.canonical import load_canonical

        for showcase_id in RECIPES:
            showcase = ROOT / "examples" / "showcase" / showcase_id
            committed = load_canonical(showcase / "evidence" / "canonical.json")
            fresh = build_canonical(showcase, ROOT, timestamp=committed.timestamp)
            assert fresh.status is committed.status, showcase_id
            assert fresh.extracted_value == committed.extracted_value, showcase_id
            assert fresh.output_file_hashes == committed.output_file_hashes, showcase_id
            assert fresh.evidence_id == committed.evidence_id, showcase_id

    def test_recorded_output_hashes_match_the_files_on_disk(self) -> None:
        """Detects a solver output edited after its evidence was written."""
        from textlayout.evidence.canonical import load_canonical

        for showcase in iter_showcases(ROOT):
            record = load_canonical(showcase / "evidence" / "canonical.json")
            assert record.verify_output_hashes(showcase) == [], showcase.name

    def test_resonator_is_invalid_and_publishes_no_value(self) -> None:
        from textlayout.evidence.canonical import load_canonical

        record = load_canonical(
            ROOT / "examples/showcase/05_quarter_wave_resonator_6ghz/evidence/canonical.json"
        )
        assert record.status.value == "SIMULATION_INVALID"
        assert record.extracted_value is None
        assert record.confidence_class.name == "NONE"
        # the withdrawn 3.0 GHz survives only as audit history
        assert record.superseded is not None
        assert record.superseded.extracted_value == 3.0

    def test_spiral_is_executed_not_verified_for_want_of_convergence(self) -> None:
        from textlayout.evidence.canonical import load_canonical

        record = load_canonical(
            ROOT / "examples/showcase/04_spiral_inductor_3nh/evidence/canonical.json"
        )
        assert record.status.value == "SIMULATION_EXECUTED"
        assert record.extracted_value == pytest.approx(2.9583084202149, rel=1e-12)
        assert record.convergence is not None
        assert record.convergence.converged is False

    def test_cpw_value_is_reproducible_from_its_touchstone(self) -> None:
        from textlayout.evidence.canonical import load_canonical
        from textlayout.simulation.runners import extract_cpw_from_touchstone

        showcase = ROOT / "examples/showcase/02_cpw_50ohm"
        record = load_canonical(showcase / "evidence" / "canonical.json")
        recomputed = extract_cpw_from_touchstone(
            showcase / "extraction/capacitance_input/openems_result.s2p",
            frequency_ghz=record.extraction_config["frequency_ghz"],
        )["characteristic_impedance_ohm"]
        assert record.extracted_value == pytest.approx(recomputed, rel=1e-12)
        assert record.status.value == "PHYSICS_VERIFIED"


class TestNoStaleGeneratedArtifacts:
    """A clean checkout must have no generated-file drift."""

    def _run(self, script: str) -> int:
        import subprocess
        import sys

        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), "--check"],
            cwd=ROOT, capture_output=True, text=True,
        ).returncode

    def test_canonical_records_are_current(self) -> None:
        assert self._run("build_canonical_evidence.py") == 0

    def test_derived_artifacts_are_current(self) -> None:
        assert self._run("render_showcase_artifacts.py") == 0


class TestDeclaredStatusExtraction:
    """A document's status is the one it *declares*, not one it merely mentions.

    Every showcase row states its quantity status and then, separately, that the
    design has no fabrication signoff. Reading "whichever status token appears
    anywhere" conflates two orthogonal scopes and silently reclassifies a
    PHYSICS_VERIFIED impedance as NOT_FABRICATION_READY.
    """

    def test_the_declared_marker_beats_tokens_mentioned_in_prose(self) -> None:
        block = (
            "- **Status:** `SIMULATION_INVALID`\n"
            "- Withdrawn status: `PHYSICS_VERIFIED`\n"
            "- **Fabrication readiness:** `NOT_FABRICATION_READY`\n"
        )
        assert _first_status_token(block) == "SIMULATION_INVALID"

    def test_a_readme_row_declares_its_leading_status(self) -> None:
        row = (
            "| 2 | CPW | **PHYSICS_VERIFIED** — openEMS extracted 49.71 ohm. "
            "**NOT_FABRICATION_READY** |"
        )
        assert _first_status_token(row) == "PHYSICS_VERIFIED"

    def test_convergence_failed_is_not_read_as_the_failed_inside_it(self) -> None:
        assert _first_status_token("status: CONVERGENCE_FAILED") == "CONVERGENCE_FAILED"

    def test_text_with_no_status_declares_nothing(self) -> None:
        assert _first_status_token("a CPW feedline on silicon") is None

    def test_every_contract_status_is_scannable(self) -> None:
        """A status added to the contract cannot escape the consistency scan."""
        for status in EvidenceStatus:
            assert status.value in _STATUS_TOKENS
