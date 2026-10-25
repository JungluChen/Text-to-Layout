import hashlib
import json
from pathlib import Path

import pytest

from textlayout.external.qeda_reference import REFERENCE_SHA256, assess_probe_pad_reference

ROOT = Path(__file__).resolve().parents[2]
BASE = (ROOT / 'docs/progress/evidence/2026-10-23-220348/baseline.kicad_mod').read_bytes()


def test_exact_geometry_and_independent_predeclared_reference():
    reference = ROOT / 'docs/progress/evidence/2026-10-23-100753/reference.json'
    assert hashlib.sha256(reference.read_bytes()).hexdigest() == REFERENCE_SHA256
    saved = json.loads(reference.read_bytes())
    result = assess_probe_pad_reference(BASE)
    assert result.pad_reference_matches and result.max_absolute_error_mm == 0
    assert len(result.comparisons) == 8
    assert result.absolute_tolerance_mm == saved['absolute_tolerance_mm']
    assert result.module_sha256 == hashlib.sha256(BASE).hexdigest()
    for c in result.comparisons:
        assert c.expected_mm == saved['pads'][str(c.pad_number)][c.quantity]


@pytest.mark.parametrize(('value', 'passes', 'error'), [
    (b'-1.499999001', True, .000000999),
    (b'-1.499999', True, .000001),
    (b'-1.499998999', False, .000001001),
    (b'-1.500001', True, .000001),
    (b'-1.500001001', False, .000001001),
    (b'-1.499', False, .001),
])
def test_fixed_threshold_both_sides(value, passes, error):
    r = assess_probe_pad_reference(BASE.replace(b'(at -1.500 0.000)', b'(at '+value+b' 0.000)'))
    assert r.pad_reference_matches is passes
    assert r.max_absolute_error_mm == error


@pytest.mark.parametrize(('old', 'new'), [
    (b'(at 1.500 0.000)', b'(at 1.500 0.100)'),
    (b'(size 1.000 1.500)', b'(size 1.100 1.500)'),
    (b'(size 1.000 1.500)', b'(size 1.000 1.600)'),
])
def test_other_dimensions_report_mismatch(old, new):
    r = assess_probe_pad_reference(BASE.replace(old, new))
    assert not r.pad_reference_matches and r.max_absolute_error_mm == .1


@pytest.mark.parametrize('case', ['backside_module', 'extra_copper', 'pad_drill', 'unclosed_quote'])
def test_invalid_structure_never_returns_reference_match(case):
    raw = (ROOT / f'docs/progress/evidence/2026-10-23-220348/{case}.kicad_mod').read_bytes()
    with pytest.raises(ValueError):
        assess_probe_pad_reference(raw)


def test_margin_not_part_of_pad_dimension_reference():
    # Explicit scope boundary: this is not complete geometry/fabrication acceptance.
    assert assess_probe_pad_reference(BASE.replace(b'solder_mask_margin 0.050', b'solder_mask_margin 0.060')).pad_reference_matches


def test_callers_decimal_precision_does_not_change_threshold():
    from decimal import localcontext

    raw = BASE.replace(b'(at -1.500 0.000)', b'(at -1.499998999 0.000)')
    with localcontext() as context:
        context.prec = 1
        result = assess_probe_pad_reference(raw)
    assert not result.pad_reference_matches
    assert result.max_absolute_error_mm == .000001001
