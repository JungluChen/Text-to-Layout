"""Tests that verify the artifact validation layer blocks fake or missing solver output.

Mission invariant: if a solver claims "executed" but the expected artifact is
absent, status must become "failed" — the report must NOT say it passed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ── validate_all_artifacts ─────────────────────────────────────────────────────

def test_validate_all_artifacts_fails_if_any_solver_missing() -> None:
    """validate_all_artifacts must fail if any solver has no artifact."""
    from text_to_gds.artifact_validator import validate_all_artifacts

    results = {
        "josephsoncircuits": {
            "status": "executed",
            "frequencies_ghz": [5.0, 5.5, 6.0],
            "gain_db": [10.0, 18.0, 10.0],
        },
        "openems": {
            "status": "executed",
            # No touchstone_path → must fail
        },
    }
    summary = validate_all_artifacts(results)
    assert summary["all_passed"] is False
    assert "openems" in summary["failed"]


def test_validate_all_artifacts_passes_if_all_skipped() -> None:
    """validate_all_artifacts accepts all-skipped — skipped is honest."""
    from text_to_gds.artifact_validator import validate_all_artifacts

    results = {
        "josephsoncircuits": {"status": "skipped", "reason": "Julia not found"},
        "openems": {"status": "skipped", "reason": "octave not installed"},
        "elmer": {"status": "skipped", "reason": "ElmerSolver not on PATH"},
    }
    summary = validate_all_artifacts(results)
    assert summary["all_passed"] is True
    assert summary["failed"] == []


def test_validate_all_artifacts_fails_completely_empty_executed() -> None:
    """A solver that reports executed with empty dict must fail."""
    from text_to_gds.artifact_validator import validate_all_artifacts

    results = {
        "scqubits": {"status": "executed"},   # no eigenvalues
    }
    summary = validate_all_artifacts(results)
    assert summary["all_passed"] is False


# ── CPW analytical model writes valid Touchstone ───────────────────────────────

def test_cpw_model_writes_valid_touchstone(tmp_path: Path) -> None:
    """cpw_model.compute_cpw_resonator must write a parseable Touchstone file."""
    from text_to_gds.physics.cpw_model import compute_cpw_resonator

    ts_path = tmp_path / "cpw_analytical.s2p"
    result = compute_cpw_resonator(
        center_width_um=10.0,
        gap_um=6.0,
        substrate_thickness_um=254.0,
        epsilon_r=11.45,
        target_frequency_ghz=6.0,
        target_bandwidth_mhz=10.0,
        touchstone_path=ts_path,
    )

    assert result["status"] == "ok", f"CPW model failed: {result.get('reason')}"
    assert ts_path.is_file(), "Touchstone file was not written"

    content = ts_path.read_text(encoding="utf-8")
    data_lines = [l for l in content.splitlines() if l.strip() and not l.startswith("!") and not l.startswith("#")]
    assert len(data_lines) >= 10, "Touchstone file has too few data lines"

    # Verify each data line has at least 9 numeric fields (f + 4×(Re,Im))
    for line in data_lines[:3]:
        parts = line.split()
        assert len(parts) >= 9, f"Touchstone line has wrong field count: {line!r}"
        for p in parts:
            float(p)  # must parse as float


def test_cpw_model_provenance_labels_analytical() -> None:
    """cpw_model result must carry method='analytical', not 'simulated'."""
    from text_to_gds.physics.cpw_model import compute_cpw_resonator

    result = compute_cpw_resonator(
        center_width_um=10.0,
        gap_um=6.0,
        substrate_thickness_um=254.0,
        epsilon_r=11.45,
        target_frequency_ghz=6.0,
    )
    prov = result.get("provenance", {})
    assert prov.get("method") == "analytical", "CPW model must label provenance as analytical"
    assert prov.get("confidence", 1.0) < 0.9, "Analytical model must not claim high confidence"


# ── resistance extractor produces structured output ───────────────────────────

def test_resistance_extractor_via_chain(tmp_path: Path) -> None:
    """extract_resistance must produce resistance_ohm and provenance for via chain."""
    from text_to_gds.resistance_extractor import extract_resistance

    sidecar = {
        "schema": "text-to-gds.sidecar.v0",
        "pcell": "via_chain_monitor",
        "parameters": {"stage_count": 100, "trace_width_um": 2.0},
        "device_info": {},
    }
    sc_path = tmp_path / "test.sidecar.json"
    sc_path.write_text(json.dumps(sidecar), encoding="utf-8")

    result = extract_resistance(sc_path)
    assert result["status"] == "executed", f"Expected executed, got: {result}"
    assert "resistance_ohm" in result
    assert result["resistance_ohm"] >= 0.0
    prov = result.get("provenance", {})
    assert prov.get("method") == "geometry_extracted"
    assert prov.get("source", "").startswith("sidecar")


# ── JJ array characterization produces geometry-extracted table ───────────────

def test_jj_array_characterization_no_julia(tmp_path: Path) -> None:
    """characterize_jj_array must produce geometry-extracted Ic/Lj table even without Julia."""
    from text_to_gds.jj_array_characterization import characterize_jj_array

    sidecar = {
        "schema": "text-to-gds.sidecar.v0",
        "pcell": "jj_ic_calibration_array",
        "parameters": {"stage_count": 5, "junction_count": 5},
        "junctions": [
            {"width_um": 0.20, "height_um": 0.20},
            {"width_um": 0.25, "height_um": 0.25},
            {"width_um": 0.30, "height_um": 0.30},
            {"width_um": 0.35, "height_um": 0.35},
            {"width_um": 0.40, "height_um": 0.40},
        ],
    }
    sc_path = tmp_path / "calibration.sidecar.json"
    sc_path.write_text(json.dumps(sidecar), encoding="utf-8")

    result = characterize_jj_array(sc_path, julia_executable=None)
    assert result["status"] == "executed"
    assert len(result["junctions"]) == 5

    for j in result["junctions"]:
        assert j["ic_ua"] > 0, "Ic must be positive"
        assert j["lj_ph"] > 0, "Lj must be positive"
        assert j["method"] == "geometry_extracted"

    summary = result["summary"]
    assert summary["ic_min_ua"] < summary["ic_max_ua"]
    assert summary["lj_min_ph"] > 0.0
