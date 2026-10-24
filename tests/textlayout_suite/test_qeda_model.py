import hashlib

import pytest

from textlayout.external.qeda_model import decode_model_reference

MODEL = b'(model Resistor_PROBERESISTOR.wrl (at (xyz 0 0 0)) (scale (xyz 0.3937 0.3937 0.3937)) (rotate (xyz 0 0 0)))'
NAME = 'Resistor_PROBERESISTOR.wrl'


def test_explicit_identity_and_raw_hash():
    result = decode_model_reference(MODEL, expected_basename=NAME)
    assert result.basename == NAME and result.scale == (.3937, .3937, .3937)
    assert result.zero_translation and result.zero_rotation
    assert result.raw_sha256 == hashlib.sha256(MODEL).hexdigest()


@pytest.mark.parametrize('name', ['../x.wrl', '/x.wrl', 'C:\\x.wrl', 'x/y.wrl',
                                  'x.wrl/..', 'x.WRL', 'x wrl', 'é.wrl',
                                  'a'*129+'.wrl', 'x.wrl\n', '${X}.wrl'])
def test_expected_basename_is_not_a_path(name):
    with pytest.raises(ValueError):
        decode_model_reference(MODEL, expected_basename=name)


@pytest.mark.parametrize(('old', 'new'), [
    (b'Resistor_PROBERESISTOR.wrl', b'wrong.wrl'),
    (b'Resistor_PROBERESISTOR.wrl', b'"Resistor_PROBERESISTOR.wrl"'),
    (b'(at (xyz 0 0 0))', b'(at (xyz 0.000000001 0 0))'),
    (b'(at (xyz 0 0 0))', b'(at (xyz 0 0 0) (extra 1))'),
    (b'(at (xyz 0 0 0))', b'(at (xy 0 0 0))'),
    (b'(at (xyz 0 0 0))', b'(at (xyz 0 0))'),
    (b'(at (xyz 0 0 0))', b'(at (xyz 0 0 0 0))'),
    (b'(at (xyz 0 0 0))', b'(at (xyz (zero) 0 0))'),
    (b'0.3937', b'0.393700001'), (b'0.3937', b'nan'),
    (b'0.3937', b'3.937e-1'), (b'0.3937', b'"0.3937"'),
    (b'rotate', b'at'), (b'rotate', b'offset'),
    (b'(rotate (xyz 0 0 0))', b''),
    (b'(rotate (xyz 0 0 0))', b'(rotate (xyz 0 0 0)) (hide yes)'),
])
def test_changed_or_malformed_records_rejected(old, new):
    with pytest.raises(ValueError):
        decode_model_reference(MODEL.replace(old, new), expected_basename=NAME)


def test_decimal_equivalence_and_no_file_lookup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = decode_model_reference(MODEL.replace(b'0.3937', b'+0.393700000'), expected_basename=NAME)
    assert result.basename == NAME
    assert list(tmp_path.iterdir()) == []
