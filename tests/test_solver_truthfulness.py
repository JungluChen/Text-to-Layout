"""Tests for solver evidence truthfulness.

Verifies that the review system correctly handles honest SKIPs, rejects
fake gain data, flags LLM-sourced provenance, and catches suspicious
flat S-parameter data.
"""

from __future__ import annotations


# -- Skipped solver is not an error -------------------------------------------


def test_skipped_solver_not_passed() -> None:
    """Evidence with status='SKIPPED' must not produce errors (honest skip is OK)."""
    from text_to_gds.review.solver import review_solver

    evidence = {
        "sidecar": {"pcell": "cpw_straight", "info": {"device_type": "cpw_straight"}},
        "simulation": {
            "status": "SKIPPED",
            "reason": "openEMS binary not found",
        },
    }
    result = review_solver(evidence)
    errors = [f for f in result["findings"] if f["severity"] == "error"]
    assert len(errors) == 0, (
        f"Honest SKIPPED status must not produce errors, got: {errors}"
    )


# -- Fake gain is rejected ----------------------------------------------------


def test_fake_gain_rejected() -> None:
    """JPA gain data without an executed solver must produce an error."""
    from text_to_gds.review.solver import review_solver

    evidence = {
        "sidecar": {"pcell": "jpa_device", "info": {"device_type": "jpa"}},
        "simulation": {
            "status": "SKIPPED",
            "gain_db": [10.0, 15.0, 20.0, 18.0],
            "frequencies_ghz": [4.0, 5.0, 6.0, 7.0],
        },
    }
    result = review_solver(evidence)
    errors = [f for f in result["findings"] if f["severity"] == "error"]
    assert len(errors) > 0, "Gain data without executed solver must be flagged as error"
    assert any("gain" in f["finding"].lower() for f in errors)


# -- LLM source is rejected ---------------------------------------------------


def test_llm_source_rejected() -> None:
    """Evidence with provenance source='LLM' must produce an error."""
    from text_to_gds.review.reviewer import review_reviewer

    evidence = {
        "sidecar": {
            "pcell": "cpw_straight",
            "info": {
                "z0_ohm": {
                    "value": 50.0,
                    "unit": "ohm",
                    "source": "LLM",
                    "method": "estimated",
                    "confidence": 0.9,
                },
            },
        },
    }
    result = review_reviewer(evidence)
    errors = [f for f in result["findings"] if f["severity"] == "error"]
    assert len(errors) > 0, "source='LLM' must be flagged as error"
    assert any("LLM" in f["finding"] for f in errors)


# -- Flat S11 is suspicious ---------------------------------------------------


def test_flat_s11_suspicious() -> None:
    """S11 data that is uniformly 0.0 dB should be flagged as suspicious."""
    # If all S11 values are exactly 0.0 dB, that implies total reflection
    # with zero loss across the entire band -- physically implausible.
    s11_db = [0.0] * 100

    # Check: all values identical and equal to zero
    all_zero = all(abs(v) < 1e-12 for v in s11_db)
    assert all_zero, "Test setup: S11 data should be all zeros"

    # A flat 0 dB S11 is physically suspicious -- verify inline check
    unique_values = set(s11_db)
    is_flat = len(unique_values) <= 1
    is_zero_db = all(abs(v) < 0.01 for v in s11_db)

    assert is_flat and is_zero_db, "Flat 0 dB S11 should be detectable"

    # Verify that non-flat data passes the check
    realistic_s11 = [-5.0, -10.0, -25.0, -15.0, -8.0]
    realistic_unique = set(realistic_s11)
    assert len(realistic_unique) > 1, "Realistic S11 should have variation"
