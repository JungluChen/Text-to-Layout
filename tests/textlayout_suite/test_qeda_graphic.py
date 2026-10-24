import hashlib

import pytest

from textlayout.external.qeda_graphic import decode_planar_graphic

LINE = b'(fp_line (start -1 0) (end 1 0) (layer F.SilkS) (width 0.12))'


def test_line_units_and_raw_identity():
    result = decode_planar_graphic(LINE)
    assert result.origin_mm == (-1, 0) and result.end_mm == (1, 0)
    assert result.width_mm == .12 and result.kind == 'fp_line'
    assert result.raw_sha256 == hashlib.sha256(LINE).hexdigest()


def test_circle_and_field_order():
    result = decode_planar_graphic(
        b'(fp_circle (width .050) (layer F.CrtYd) (center 0 0) (end 0 1))'.replace(b'.050', b'0.050')
    )
    assert result.kind == 'fp_circle' and result.origin_mm == (0, 0)
    assert result.end_mm == (0, 1) and result.width_mm == .05


@pytest.mark.parametrize(('old', 'new'), [
    (b'F.SilkS', b'F.Cu'), (b'F.SilkS', b'B.Cu'), (b'F.SilkS', b'In1.Cu'),
    (b'F.SilkS', b'B.SilkS'), (b'F.SilkS', b'"F.SilkS"'),
    (b'width 0.12', b'width 0'), (b'width 0.12', b'width -1'),
    (b'width 0.12', b'width nan'), (b'width 0.12', b'width 1e309'),
    (b'start -1 0', b'start 1 0'), (b'start -1 0', b'start -1 0 0'),
    (b'start -1 0', b'start (x -1) 0'), (b'start -1 0', b'start -1001 0'),
    (b'end 1 0', b'start 1 0'), (b'end 1 0', b'center 1 0'),
    (b'layer F.SilkS', b'layer F.SilkS (pad 3)'),
    (b'width 0.12', b'width 0.12 1'), (b'fp_line', b'fp_arc'),
    (b'(width 0.12)', b'(width 0.12) (drill 1)'),
    (b'(width 0.12)', b''),
])
def test_corrupted_graphics_rejected(old, new):
    with pytest.raises(ValueError):
        decode_planar_graphic(LINE.replace(old, new))


def test_degenerate_circle_rejected():
    with pytest.raises(ValueError):
        decode_planar_graphic(b'(fp_circle (center 0 0) (end 0 0) (layer F.Fab) (width 1))')


def test_schema_does_not_establish_reference_agreement():
    assert decode_planar_graphic(LINE.replace(b'end 1 0', b'end 99 0')).end_mm == (99, 0)
