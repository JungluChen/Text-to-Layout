import hashlib

import pytest

from textlayout.external.qeda_text import decode_text_annotation

REF = b'(fp_text reference REF** (at 0 0) (layer F.SilkS) (effects (font (size 1.2 1.2) (thickness 0.12))))'


def test_reference_dimensions_and_identity():
    r = decode_text_annotation(REF, expected_text='REF**')
    assert r.role == 'reference' and not r.hidden and r.layer == 'F.SilkS'
    assert r.position_mm == (0, 0) and r.font_size_mm == (1.2, 1.2)
    assert r.thickness_mm == .12 and r.raw_sha256 == hashlib.sha256(REF).hexdigest()


def test_value_and_hidden_user():
    value = REF.replace(b'reference REF**', b'value Probe').replace(b'F.SilkS', b'F.Fab')
    assert decode_text_annotation(value, expected_text='Probe').text == 'Probe'
    user = REF.replace(b'reference', b'user').replace(b'F.SilkS', b'F.Fab').replace(b'(at 0 0)', b'(at 0 0 0) hide')
    assert decode_text_annotation(user, expected_text='REF**').hidden


@pytest.mark.parametrize(('old', 'new'), [
    (b'F.SilkS', b'F.Cu'), (b'F.SilkS', b'F.Fab'),
    (b'REF**', b'OTHER'), (b'REF**', b'"REF**"'),
    (b'reference', b'unknown'), (b'reference', b'user'),
    (b'(at 0 0)', b'(at 0 0 90)'), (b'(at 0 0)', b'(at 0 0 0 0)'),
    (b'(at 0 0)', b'(at nan 0)'), (b'(at 0 0)', b'(at 0 0) hide'),
    (b'(size 1.2 1.2)', b'(size 0 1.2)'),
    (b'(size 1.2 1.2)', b'(size 1.2)'),
    (b'(thickness 0.12)', b'(thickness -1)'),
    (b'(thickness 0.12)', b'(thickness (x 1))'),
    (b'(thickness 0.12)', b'(size 1 1)'),
    (b'(thickness 0.12)', b'(thickness 0.12) (bold yes)'),
    (b'(layer F.SilkS)', b'(layer F.SilkS) (pad 3 smd rect)'),
    (b'(layer F.SilkS)', b'(at 0 0)'),
    (b'(layer F.SilkS)', b''),
    (b'font', b'font (pad 3)'),
])
def test_corruptions_rejected(old, new):
    with pytest.raises(ValueError):
        decode_text_annotation(REF.replace(old, new), expected_text='REF**')


@pytest.mark.parametrize('text', ['', 'a b', 'x/y', 'é', 'x'*129])
def test_invalid_expected_identity(text):
    with pytest.raises(ValueError):
        decode_text_annotation(REF, expected_text=text)


def test_schema_is_not_placement_reference():
    assert decode_text_annotation(REF.replace(b'at 0 0', b'at 99 0'), expected_text='REF**').position_mm == (99, 0)
