"""Acceptance tests for solver-evidence honesty and provenance."""

from __future__ import annotations

import pytest

from text_to_gds.evidence import evidence_bundle, solver_evidence
from text_to_gds.jpa_analysis import _post_process

_REQUIRED_FIELDS = {
    "quantity",
    "source_device",
    "source_sidecar",
    "solver_name",
    "solver_status",
    "input_file",
    "output_file",
    "frequency_range_ghz",
    "timestamp",
}


def test_every_record_has_full_provenance():
    rec = solver_evidence(
        quantity="gain_db",
        source_device="JPA 6 GHz",
        source_sidecar="sidecar.json",
        solver_name="JosephsonCircuits.jl",
        solver_status="SKIPPED",
        input_file="in.json",
        frequency_range_ghz=[5.9, 6.1],
    )
    assert _REQUIRED_FIELDS <= set(rec)


def test_executed_without_output_file_is_downgraded():
    rec = solver_evidence(
        quantity="f01_ghz",
        source_device="transmon",
        source_sidecar=None,
        solver_name="scqubits",
        solver_status="EXECUTED",
        output_file="C:/does/not/exist_12345.json",
        value=5.0,
    )
    assert rec["solver_status"] == "FAILED"
    assert rec["value"] is None
    assert "downgraded" in (rec["notes"] or "")


def test_executed_with_real_output_file_stays_executed(tmp_path):
    out = tmp_path / "result.json"
    out.write_text('{"f01_ghz": 5.0}', encoding="utf-8")
    rec = solver_evidence(
        quantity="f01_ghz",
        source_device="transmon",
        source_sidecar=None,
        solver_name="scqubits",
        solver_status="EXECUTED",
        output_file=out,
        value=5.0,
    )
    assert rec["solver_status"] == "EXECUTED"
    assert rec["output_file_exists"] is True


def test_invalid_status_rejected():
    with pytest.raises(ValueError):
        solver_evidence(
            quantity="x", source_device="d", source_sidecar=None,
            solver_name="s", solver_status="DONE",
        )


def test_bundle_lists_skipped_and_executed():
    items = [
        solver_evidence(quantity="a", source_device="d", source_sidecar=None,
                        solver_name="s", solver_status="SKIPPED"),
        solver_evidence(quantity="b", source_device="d", source_sidecar=None,
                        solver_name="s", solver_status="PREPARED"),
    ]
    bundle = evidence_bundle(device="d", source_sidecar=None, items=items)
    assert bundle["executed_quantities"] == []
    assert {s["quantity"] for s in bundle["skipped_quantities"]} == {"a"}


def test_quantum_efficiency_skipped_without_solver_value():
    # No best_efficiency in the sweep -> efficiency-derived metrics are SKIPPED,
    # never a fabricated flat 1.0.
    result = {
        "center_frequency_ghz": 6.0,
        "pump_fractions": [0.01, 0.02],
        "peak_gain_db": [10.0, 20.0],
        "pump_currents_a": [1e-8, 2e-8],
        "best_peak_gain_db": 20.0,
    }
    metrics = _post_process(result, signal_bandwidth_hz=2e8)
    assert metrics["quantum_efficiency"] is None
    assert metrics["quantum_efficiency_status"] == "SKIPPED"
    assert metrics["noise_temperature_k"] is None


def test_quantum_efficiency_used_when_solver_provides_it():
    result = {
        "center_frequency_ghz": 6.0,
        "pump_fractions": [0.01, 0.02],
        "peak_gain_db": [10.0, 20.0],
        "pump_currents_a": [1e-8, 2e-8],
        "best_peak_gain_db": 20.0,
        "best_efficiency": 0.8,
    }
    metrics = _post_process(result, signal_bandwidth_hz=2e8)
    assert metrics["quantum_efficiency"] == pytest.approx(0.8)
    assert metrics["quantum_efficiency_status"] == "EXECUTED"
    assert metrics["noise_temperature_k"] is not None
