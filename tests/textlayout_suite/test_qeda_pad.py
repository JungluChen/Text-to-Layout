import hashlib
from dataclasses import FrozenInstanceError

import pytest

from textlayout.external.qeda_pad import decode_rectangular_pad

PAD = b'''(pad 1 smd rect (at -1.500 0.000) (size 1.000 1.500)
(layers F.Cu F.Mask F.Paste) (solder_mask_margin 0.050))'''


def test_dimensions_identity_and_raw_hash():
    result = decode_rectangular_pad(PAD)
    assert (result.number, result.x_mm, result.y_mm) == (1, -1.5, 0)
    assert (result.width_mm, result.height_mm, result.solder_mask_margin_mm) == (1, 1.5, .05)
    assert result.raw_sha256 == hashlib.sha256(PAD).hexdigest()
    assert decode_rectangular_pad(PAD + b'\n').raw_sha256 != result.raw_sha256
    with pytest.raises(FrozenInstanceError):
        result.number = 2


@pytest.mark.parametrize(('old', 'new'), [
    (b'pad 1', b'pad 3'), (b'pad 1', b'pad "1"'), (b'smd', b'thru_hole'),
    (b'rect', b'circle'), (b'F.Cu', b'B.Cu'), (b'F.Cu', b'F.Cu F.Cu'),
    (b'0.000)', b'0.000 90)'), (b'(size 1.000 1.500)', b'(size 0 1.5)'),
    (b'(size 1.000 1.500)', b'(size -1 1.5)'),
    (b'(solder_mask_margin 0.050)', b'(drill 0.8)'),
    (b'(solder_mask_margin 0.050)', b'(at 0 0)'),
    (b'(solder_mask_margin 0.050)', b'(solder_mask_margin -0.1)'),
    (b'(solder_mask_margin 0.050)', b'(solder_mask_margin 0.05 1)'),
    (b'(size 1.000 1.500)', b'(size (x 1) 1.5)'),
    (b'(solder_mask_margin 0.050)', b''),
    (b'(solder_mask_margin 0.050)', b'(solder_mask_margin 0.05) (drill 0.8)'),
])
def test_fields_fail_closed(old, new):
    with pytest.raises(ValueError):
        decode_rectangular_pad(PAD.replace(old, new))


@pytest.mark.parametrize('value', [b'nan', b'inf', b'-inf', b'1e309', b'1e-999',
                                 b'1000.000000001', b'-1001', b'0.0000000001',
                                 b'"1"', b'1_000', b'0x1', b'10000'])
def test_invalid_dimensions(value):
    with pytest.raises(ValueError):
        decode_rectangular_pad(PAD.replace(b'-1.500', value))


def test_supported_boundaries_and_number_two():
    pad = PAD.replace(b'pad 1', b'pad 2').replace(b'-1.500', b'-1000')
    pad = pad.replace(b'(size 1.000 1.500)', b'(size 0.000000001 1000)')
    result = decode_rectangular_pad(pad)
    assert result.number == 2 and result.x_mm == -1000
    assert result.width_mm == 1e-9 and result.height_mm == 1000


def test_schema_is_not_reference_comparison():
    # A supported but wrong-for-the-reference position must not be called accepted.
    assert decode_rectangular_pad(PAD.replace(b'-1.500', b'-1.400')).x_mm == -1.4
