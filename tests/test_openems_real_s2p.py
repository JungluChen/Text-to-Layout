"""Tests for openEMS S-parameter artifact requirements.

These tests verify the runner's behavior when openEMS is available/unavailable
without requiring a real openEMS installation.  The key invariants:
  - If openEMS is not found: status="skipped", never "failed" or "passed"
  - If octave is not found: status="skipped" with explicit reason mentioning octave
  - If openEMS runs but produces no .s2p: status="failed" with explanation
  - Never synthesize S-parameters
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ?€?€ helpers ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€

def _write_extraction(tmp_path: Path, *, resonance_hz: float = 6e9) -> Path:
    """Write a minimal extraction.json that satisfies the openEMS runner schema."""
    ext = {
        "schema": "text-to-gds.extraction.v1",
        "linear_circuit": {
            "resonance_frequency": resonance_hz,
        },
        "solver_inputs": {
            "openems": {
                "epsilon_r": 11.45,
                "substrate_thickness_um": 254.0,
            }
        },
    }
    p = tmp_path / "test_extraction.json"
    p.write_text(json.dumps(ext), encoding="utf-8")
    return p


# ?€?€ openEMS binary not found ??SKIPPED ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€

def test_openems_missing_binary_returns_skipped(tmp_path: Path) -> None:
    """When the openEMS executable is missing, runner must return status=skipped."""
    from text_to_gds.openems_runner import run_openems

    ext_path = _write_extraction(tmp_path)
    result = run_openems(
        ext_path,
        sim_dir=tmp_path / "sim",
        report_path=tmp_path / "report.json",
        openems_executable=str(tmp_path / "nonexistent_openems"),
    )
    assert result["status"] == "skipped", f"Expected skipped, got: {result['status']!r}"
    assert "executed" not in result.get("reason", "").lower() or not result.get("executed")


# ?€?€ octave not found ??SKIPPED with explanation ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€

def test_openems_no_octave_returns_skipped_with_explanation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If openEMS binary exists but octave is not installed, return skipped with octave reason."""
    import text_to_gds.openems_runner as runner_mod
    from text_to_gds.openems_runner import run_openems

    # Patch _find_octave to simulate no octave
    monkeypatch.setattr(runner_mod, "_find_octave", lambda: None)

    # Create a fake openEMS executable that exits 0
    fake_exe = tmp_path / "fake_openems.bat"
    fake_exe.write_text("@echo off\r\nexit 0\r\n", encoding="utf-8")

    ext_path = _write_extraction(tmp_path)
    result = run_openems(
        ext_path,
        sim_dir=tmp_path / "sim",
        report_path=tmp_path / "report.json",
        openems_executable=str(fake_exe),
    )

    assert result["status"] == "skipped"
    assert "octave" in result["reason"].lower() or "post-process" in result["reason"].lower()


# ?€?€ extraction missing resonance_frequency ??FAILED ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€

def test_openems_missing_resonance_returns_failed(tmp_path: Path) -> None:
    """If extraction.json has no resonance_frequency, runner must fail with explanation."""
    from text_to_gds.openems_runner import run_openems

    ext = {
        "schema": "text-to-gds.extraction.v1",
        "linear_circuit": {},  # no resonance_frequency
    }
    ext_path = tmp_path / "no_resonance.json"
    ext_path.write_text(json.dumps(ext), encoding="utf-8")

    result = run_openems(
        ext_path,
        sim_dir=tmp_path / "sim",
        report_path=tmp_path / "report.json",
        openems_executable=str(tmp_path / "nonexistent"),
    )
    # Should fail (missing field) or skip (no binary) ??never succeed
    assert result["status"] in ("failed", "skipped")


# ?€?€ Touchstone validation: no .s2p ??artifact validator catches it ?€?€?€?€?€?€?€?€?€?€?€?€?€

def test_artifact_validator_rejects_openems_without_s2p(tmp_path: Path) -> None:
    """artifact_validator must reject openEMS result with no Touchstone path."""
    from text_to_gds.artifact_validator import validate_artifact

    fake_result = {
        "status": "executed",
        # No touchstone_path field
    }
    check = validate_artifact("openems", fake_result)
    assert check["passed"] is False
    assert check["status"] == "failed"
    assert "touchstone" in check["reason"].lower()


def test_artifact_validator_rejects_openems_missing_file(tmp_path: Path) -> None:
    """artifact_validator must reject openEMS result where Touchstone file doesn't exist."""
    from text_to_gds.artifact_validator import validate_artifact

    fake_result = {
        "status": "executed",
        "touchstone_path": str(tmp_path / "does_not_exist.s2p"),
    }
    check = validate_artifact("openems", fake_result)
    assert check["passed"] is False
    assert check["status"] == "failed"


def test_artifact_validator_accepts_openems_with_real_s2p(tmp_path: Path) -> None:
    """artifact_validator accepts openEMS result with a real Touchstone file."""
    from text_to_gds.artifact_validator import validate_artifact

    s2p = tmp_path / "output.s2p"
    s2p.write_text(
        "# Hz S RI R 50\n"
        "1e9 0.1 0.0 0.9 0.0 0.9 0.0 0.1 0.0\n"
        "2e9 0.2 0.0 0.8 0.0 0.8 0.0 0.2 0.0\n",
        encoding="utf-8",
    )

    result = {"status": "executed", "touchstone_path": str(s2p)}
    check = validate_artifact("openems", result)
    assert check["passed"] is True


# ?€?€ openEMS skipped is valid (honest reporting) ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€

def test_artifact_validator_accepts_openems_skipped(tmp_path: Path) -> None:
    """artifact_validator must accept openEMS skipped ??SKIPPED is honest, not a failure."""
    from text_to_gds.artifact_validator import validate_artifact

    result = {"status": "skipped", "reason": "openEMS not installed"}
    check = validate_artifact("openems", result)
    assert check["passed"] is True
    assert check["status"] == "skipped"
