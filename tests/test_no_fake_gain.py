"""Tests that verify JPA gain is always sourced from JosephsonCircuits.jl.

Key invariant: source = "LLM" or synthetic gain ??immediate test failure.
Any gain curve must trace to an executed JosephsonCircuits.jl result.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _jpa_result_with_gain(gain_source: str, gain_values: list) -> dict:
    return {
        "schema": "text-to-gds.jpa-pump-sweep.v0",
        "adapter": gain_source,
        "analysis_status": "executed",
        "frequencies_ghz": gain_values,
        "gain_db": [10.0] * len(gain_values),
    }


# ?€?€ provenance: source must never be "LLM" ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€

def test_gain_source_llm_fails_artifact_validation() -> None:
    """Any result claiming source='LLM' must be rejected by artifact validator."""
    from text_to_gds.backends.base import validate_value_records

    bad_records = {
        "peak_gain_db": {
            "value": 20.0,
            "unit": "dB",
            "source": "LLM",
            "method": "estimated",
            "confidence": 0.9,
        }
    }
    errors = validate_value_records(bad_records)
    assert errors, "validate_value_records must reject source='LLM'"
    assert any("LLM" in e for e in errors)


# ?€?€ JosephsonCircuits.jl result must have gain array ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€

def test_artifact_validator_requires_gain_array() -> None:
    """artifact_validator must reject JC.jl result with no gain array."""
    from text_to_gds.artifact_validator import validate_artifact

    result_no_gain = {
        "status": "executed",
        "adapter": "JosephsonCircuits.jl",
        "analysis_status": "executed",
        # no frequencies_ghz, no gain_db
    }
    check = validate_artifact("josephsoncircuits", result_no_gain)
    assert check["passed"] is False


def test_artifact_validator_accepts_real_gain_array() -> None:
    """artifact_validator must accept JC.jl result with a valid numerical gain array."""
    from text_to_gds.artifact_validator import validate_artifact

    result = _jpa_result_with_gain(
        "JosephsonCircuits.jl",
        [5.0 + i * 0.01 for i in range(50)],
    )
    check = validate_artifact("josephsoncircuits", result)
    assert check["passed"] is True


def test_artifact_validator_accepts_skipped_jc() -> None:
    """JC.jl skipped is valid ??Julia not installed is honest, not a failure."""
    from text_to_gds.artifact_validator import validate_artifact

    result = {"status": "skipped", "reason": "Julia not found"}
    check = validate_artifact("josephsoncircuits", result)
    assert check["passed"] is True
    assert check["status"] == "skipped"


# ?€?€ gain from JC.jl must be finite numbers ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€

def test_artifact_validator_rejects_nan_gain_array() -> None:
    """artifact_validator must reject JC.jl result where gain array contains NaN."""
    from text_to_gds.artifact_validator import validate_artifact
    import math

    result = {
        "status": "executed",
        "adapter": "JosephsonCircuits.jl",
        "analysis_status": "executed",
        "frequencies_ghz": [5.0 + i * 0.01 for i in range(10)],
        "gain_db": [math.nan] * 10,  # NaN ??invalid
    }
    check = validate_artifact("josephsoncircuits", result)
    assert check["passed"] is False


# ?€?€ scqubits eigenvalues must exist ?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€?€

def test_artifact_validator_requires_scqubits_eigenvalues() -> None:
    from text_to_gds.artifact_validator import validate_artifact

    result = {
        "status": "executed",
        "execution": {
            # No energy_levels_ghz, no f01_ghz
        }
    }
    check = validate_artifact("scqubits", result)
    assert check["passed"] is False


def test_artifact_validator_accepts_real_scqubits_result() -> None:
    from text_to_gds.artifact_validator import validate_artifact

    result = {
        "status": "executed",
        "execution": {
            "status": "executed",
            "energy_levels_ghz": [0.0, 5.03, 10.04, 15.04],
            "f01_ghz": 5.03,
            "anharmonicity_ghz": -0.017,
        }
    }
    check = validate_artifact("scqubits", result)
    assert check["passed"] is True
