import hashlib
from pathlib import Path

import pytest

from textlayout.external.qeda_module import decode_footprint_module

EVIDENCE = Path(__file__).resolve().parents[2] / 'docs/progress/evidence/2026-10-23-220348'
BASE = (EVIDENCE / 'baseline.kicad_mod').read_bytes()
NAME = 'Resistor_PROBERESISTOR'


def test_actual_complete_module_and_original_hashes():
    r = decode_footprint_module(BASE, expected_name=NAME)
    assert [p.number for p in r.pads] == [1, 2]
    assert len(r.graphics) == 13 and len(r.annotations) == 3
    assert r.raw_sha256 == hashlib.sha256(BASE).hexdigest()
    pad = BASE[BASE.index(b'(pad 1'):BASE.index(b'(pad 2')].strip()
    assert r.pads[0].raw_sha256 == hashlib.sha256(pad).hexdigest()
    assert r.model.basename == NAME + '.wrl'


@pytest.mark.parametrize('case', ['backside_module', 'extra_copper', 'pad_drill', 'unclosed_quote'])
def test_retained_corruption_corpus_rejected(case):
    with pytest.raises(ValueError):
        decode_footprint_module((EVIDENCE / (case + '.kicad_mod')).read_bytes(), expected_name=NAME)


@pytest.mark.parametrize(('old', 'new'), [
    (b'pad 2', b'pad 1'), (b'(attr smd)', b''),
    (b'(attr smd)', b'(attr smd) (attr smd)'),
    (b'(attr smd)', b'(attr smd) trailing'),
    (b'(attr smd)', b'(attr smd) (unknown (layer F.Cu))'),
    (b'(attr smd)', b'(attr smd) ()'),
    (b'(attr smd)', b'(attr smd) (fp_text)'),
    (b'(layer F.Cu)', b'(layer F.Cu extra)'),
    (b'(layer F.Cu)', b'(layer "F.Cu")'),
    (b'fp_text value', b'fp_text reference'),
    (b'fp_text user', b'fp_text value'),
    (b'Resistor_PROBERESISTOR.wrl', b'Other.wrl'),
    (b'(thickness 0.120)', b'(thickness 0.120) (pad 3 smd rect)'),
])
def test_full_tree_mutations_rejected(old, new):
    with pytest.raises(ValueError):
        decode_footprint_module(BASE.replace(old, new), expected_name=NAME)


@pytest.mark.parametrize('name', ['Wrong', '../x', 'x y', '', 'x'*129])
def test_explicit_name_rejected(name):
    with pytest.raises(ValueError):
        decode_footprint_module(BASE, expected_name=name)


def test_whitespace_preserves_component_hashes_but_changes_module_hash():
    a = decode_footprint_module(BASE, expected_name=NAME)
    b = decode_footprint_module(b'\n' + BASE + b'\n', expected_name=NAME)
    assert a.pads == b.pads and a.model == b.model
    assert a.raw_sha256 != b.raw_sha256


def test_structural_decode_is_not_geometric_reference():
    r = decode_footprint_module(BASE.replace(b'-1.500', b'-1.400'), expected_name=NAME)
    assert r.pads[0].x_mm == -1.4


@pytest.mark.parametrize('kind', [b'(pad 2', b'(model ', b'(fp_text reference'])
@pytest.mark.parametrize('duplicate', [False, True])
def test_missing_or_duplicate_required_records(kind, duplicate):
    start = BASE.index(kind)
    depth = 0
    end = start
    for end in range(start, len(BASE)):
        depth += (BASE[end] == 40) - (BASE[end] == 41)
        if depth == 0:
            break
    record = BASE[start:end + 1]
    changed = BASE[:start] + (record * 2 if duplicate else b'') + BASE[end + 1:]
    with pytest.raises(ValueError):
        decode_footprint_module(changed, expected_name=NAME)
