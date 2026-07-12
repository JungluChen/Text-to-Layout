"""Unit tests for the Python resource sampler and process-count gate."""

from __future__ import annotations

from textlayout.simulation.resource_sampler import (
    ResourceSample,
    _parse_free_mb,
    decide_process_count,
)

FREE_OUTPUT = """               total        used        free      shared  buff/cache   available
Mem:           11830        2401        9765          13         339        9428
Swap:           3072           0         3072"""


def test_parse_free_handles_plain_output_without_awk() -> None:
    budget = _parse_free_mb(FREE_OUTPUT)
    assert budget == {"total_mb": 11830, "available_mb": 9428, "used_mb": 2401}


def test_parse_free_is_safe_on_garbage() -> None:
    assert _parse_free_mb("") == {"total_mb": 0, "available_mb": 0, "used_mb": 0}
    assert _parse_free_mb("no mem line here") == {
        "total_mb": 0,
        "available_mb": 0,
        "used_mb": 0,
    }


def test_resource_sample_reports_growth() -> None:
    sample = ResourceSample(
        peak_used_mb=4000, peak_solver_rss_mb=1800, samples=42, baseline_used_mb=800
    )
    payload = sample.to_dict()
    assert payload["peak_used_mb"] == 4000
    assert payload["peak_solver_rss_mb"] == 1800
    assert payload["peak_solver_growth_mb"] == 3200
    assert payload["samples"] == 42


def test_gate_keeps_processes_when_peak_is_low() -> None:
    budget = {"total_mb": 11830, "available_mb": 11000}
    decision = decide_process_count(4, budget, preflight_peak_mb=3000)
    assert decision["accepted_processes"] == 4
    assert decision["memory_tier"] == "low"


def test_gate_caps_processes_in_the_medium_tier() -> None:
    budget = {"total_mb": 11830, "available_mb": 11000}
    decision = decide_process_count(4, budget, preflight_peak_mb=7200)  # ~65%
    assert decision["accepted_processes"] == 2
    assert decision["memory_tier"] == "medium"


def test_gate_reduces_in_the_high_tier() -> None:
    budget = {"total_mb": 11830, "available_mb": 11000}
    decision = decide_process_count(4, budget, preflight_peak_mb=9500)  # ~86%
    assert decision["accepted_processes"] == 2
    assert decision["memory_tier"] == "high"


def test_gate_is_transparent_without_a_peak_estimate() -> None:
    budget = {"total_mb": 11830, "available_mb": 11000}
    decision = decide_process_count(4, budget, preflight_peak_mb=None)
    # no silent change: the requested count is honoured and the tier is unknown
    assert decision["accepted_processes"] == 4
    assert decision["memory_tier"] == "unknown"
    assert "honouring the requested count" in decision["rationale"]
