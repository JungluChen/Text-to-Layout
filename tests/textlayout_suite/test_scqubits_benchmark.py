"""Synthetic rejection tests; real numerical packets are retained separately."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    'scq_gate', Path(__file__).resolve().parents[2] / 'scripts/check_scqubits_transmon.py')
assert spec and spec.loader
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
PLAN = json.loads(bench.PLAN.read_text())


def evidence():
    return [{'ncut':n, 'levels_hz':[0., 1e9, 2e9, 3e9, 4e9, 5e9],
             'scaled_residual':1e-16} for n in PLAN['cutoffs']]


def test_plan_identity():
    assert hashlib.sha256(bench.PLAN.read_bytes()).hexdigest() == bench.PLAN_SHA256


@pytest.mark.parametrize('failure', ['reference', 'refinement', 'residual'])
def test_rejects_failed_numerics(failure):
    rows = evidence()
    reference = copy.deepcopy(rows[-1]['levels_hz'])
    if failure == 'reference':
        reference[-1] += 2*PLAN['max_reference_hz']
    elif failure == 'refinement':
        rows[-2]['levels_hz'][-1] += 2*PLAN['max_refinement_hz']
    else:
        rows[-1]['scaled_residual'] = 2*PLAN['max_scaled_residual']
    assert not bench.assess(rows, reference, PLAN)[1]


@pytest.mark.parametrize('failure', ['missing', 'nan', 'negative', 'unordered', 'incomplete'])
def test_rejects_invalid_evidence(failure):
    rows = evidence()
    reference = copy.deepcopy(rows[-1]['levels_hz'])
    if failure == 'missing':
        rows.pop()
    elif failure == 'nan':
        reference[1] = float('nan')
    elif failure == 'negative':
        rows[0]['scaled_residual'] = -1
    elif failure == 'unordered':
        rows[0]['levels_hz'][2] = rows[0]['levels_hz'][1]
    else:
        rows[0]['levels_hz'].pop()
    with pytest.raises(ValueError):
        bench.assess(rows, reference, PLAN)
