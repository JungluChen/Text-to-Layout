"""Sprint 3: the openEMS evidence report classifies honestly, always.

The classification rules under test are the sprint's non-negotiables:
executed+in-tolerance = PHYSICS_VERIFIED; executed+off-target =
SIMULATION_EXECUTED; failed/unconverged = SIMULATION_FAILED; solver absent =
SKIPPED_SOLVER_ABSENT. A report that is anything short of verified must
carry a known-issue/diagnosis section.
"""

from __future__ import annotations

import json
from pathlib import Path

from textlayout.simulation import SimulationResult
from textlayout.simulation.openems_evidence import (
    classify,
    write_openems_evidence,
)


def _executed(within: bool, extracted: float) -> SimulationResult:
    return SimulationResult(
        status="executed",
        solver="openEMS+scikit-rf",
        readiness_level=4 if within else 3,
        reason="Extracted characteristic_impedance_ohm from solver-owned result.",
        extracted_quantities={"characteristic_impedance_ohm": extracted},
        target_comparison={
            "quantity": "characteristic_impedance_ohm",
            "extracted": extracted,
            "target": 50.0,
            "error_pct": (extracted - 50.0) / 50.0 * 100.0,
            "tolerance_pct": 5.0,
            "within_tolerance": within,
        },
        solver_version="openEMS via Octave frontend",
        runtime_seconds=1000.0,
    )


class TestClassification:
    def test_in_tolerance_executed_is_physics_verified(self) -> None:
        label, _ = classify(_executed(True, 49.9))
        assert label == "PHYSICS_VERIFIED"

    def test_off_target_executed_is_simulation_executed(self) -> None:
        """The 30-ohm-vs-50-ohm case can never be PHYSICS_VERIFIED."""
        label, reason = classify(_executed(False, 30.0))
        assert label == "SIMULATION_EXECUTED"
        assert "NOT physics-verified" in reason

    def test_failed_is_simulation_failed(self) -> None:
        result = SimulationResult(
            status="failed",
            solver="openEMS",
            readiness_level=2,
            reason="openEMS run did NOT converge: field energy decayed only -13.4 dB",
        )
        label, reason = classify(result)
        assert label == "SIMULATION_FAILED"
        assert "converge" in reason

    def test_skipped_is_solver_absent(self) -> None:
        result = SimulationResult(
            status="skipped",
            solver="openEMS",
            readiness_level=2,
            reason="octave-cli not found",
        )
        assert classify(result)[0] == "SKIPPED_SOLVER_ABSENT"

    def test_prepared_is_never_promoted(self) -> None:
        result = SimulationResult(
            status="input_files_prepared",
            solver="openEMS",
            readiness_level=2,
            reason="model generated",
        )
        label, _ = classify(result)
        assert label == "SIMULATION_INPUT_PREPARED"


class TestReportContents:
    def test_non_verified_report_has_diagnosis(self, tmp_path: Path) -> None:
        files = write_openems_evidence(
            _executed(False, 30.0),
            tmp_path,
            device_type="CPW feedline",
            target_value=50.0,
            target_unit="ohm",
            stem="cpw_openems_report",
            diagnosis=["extracted 30 ohm vs 50 ohm target"],
        )
        report = json.loads(Path(files["json"]).read_text(encoding="utf-8"))
        assert report["status"] == "SIMULATION_EXECUTED"
        assert report["known_issue"] == ["extracted 30 ohm vs 50 ohm target"]
        markdown = Path(files["markdown"]).read_text(encoding="utf-8")
        assert "Known issue" in markdown
        assert "SIMULATION_EXECUTED" in markdown

    def test_verified_report_has_no_known_issue_but_keeps_honesty(
        self, tmp_path: Path
    ) -> None:
        files = write_openems_evidence(
            _executed(True, 49.9),
            tmp_path,
            device_type="CPW feedline",
            target_value=50.0,
            target_unit="ohm",
            stem="cpw_openems_report",
        )
        report = json.loads(Path(files["json"]).read_text(encoding="utf-8"))
        assert report["status"] == "PHYSICS_VERIFIED"
        assert "known_issue" not in report
        markdown = Path(files["markdown"]).read_text(encoding="utf-8")
        assert "fabrication-ready" in markdown  # the negated honesty statement

    def test_report_carries_required_provenance_fields(self, tmp_path: Path) -> None:
        files = write_openems_evidence(
            _executed(True, 49.9),
            tmp_path,
            device_type="CPW feedline",
            target_value=50.0,
            target_unit="ohm",
            stem="cpw_openems_report",
        )
        report = json.loads(Path(files["json"]).read_text(encoding="utf-8"))
        for key in (
            "device_type",
            "target_value",
            "extracted_quantities",
            "error_percent",
            "solver_backend",
            "solver_command",
            "raw_output_paths",
            "touchstone_path",
            "model_setup",
            "convergence",
            "status",
            "reason",
            "timestamp",
        ):
            assert key in report, key
