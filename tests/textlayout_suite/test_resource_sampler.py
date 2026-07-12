"""Unit tests for the Python resource sampler and process-count gate."""

from __future__ import annotations

from textlayout.simulation.resource_sampler import (
    ResourceSample,
    decide_process_count,
)


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
