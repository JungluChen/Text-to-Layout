import hashlib
import json
from pathlib import Path

import pytest

from textlayout.external.qeda_baseline import (
    AUDIT_ID,
    AUDIT_SHA256,
    compare_audited_inventory,
)

BASELINE = Path(__file__).resolve().parents[2] / (
    'docs/progress/evidence/2026-10-26-102228/runtime-before.json'
)


def test_retained_baseline_identity_and_reordered_observation():
    raw = BASELINE.read_bytes()
    observed = json.dumps(list(reversed(json.loads(raw)))).encode()
    result = compare_audited_inventory(raw, observed)
    assert result.audit_id == AUDIT_ID
    assert result.comparison.expected_sha256 == AUDIT_SHA256
    assert result.comparison.observed_sha256 == hashlib.sha256(observed).hexdigest()
    assert result.comparison.matches_supplied_inventory


def test_substituted_baseline_cannot_self_validate():
    raw = BASELINE.read_bytes()
    rows = json.loads(raw)
    rows[0]['sha256'] = '0' * 64
    substituted = json.dumps(rows).encode()
    with pytest.raises(ValueError, match='retained QEDA audit'):
        compare_audited_inventory(substituted, substituted)


def test_reformatted_expected_bytes_are_not_the_pinned_artifact():
    raw = BASELINE.read_bytes()
    with pytest.raises(ValueError, match='retained QEDA audit'):
        compare_audited_inventory(raw + b'\n', raw)


def test_missing_observation_still_reports_every_missing_path():
    raw = BASELINE.read_bytes()
    result = compare_audited_inventory(raw, b'[]')
    assert len(result.comparison.missing) == 1084
    assert not result.comparison.matches_supplied_inventory


def test_bound_and_malformed_observation_rejected():
    with pytest.raises(ValueError, match='byte limit'):
        compare_audited_inventory(b' ' * (2 * 1024**2 + 1), b'[]')
    with pytest.raises(ValueError):
        compare_audited_inventory(BASELINE.read_bytes(), b'null')
