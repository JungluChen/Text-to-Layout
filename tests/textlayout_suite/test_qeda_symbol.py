import hashlib
from pathlib import Path

import pytest
import yaml

from textlayout.external.qeda_symbol import decode_probe_symbol

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'docs/progress/evidence/2026-10-23-160519'
RAW = (EVIDENCE / 'run-1/kicad/probe.lib').read_bytes()


def test_actual_identity_matches_input_pin_map():
    r = decode_probe_symbol(RAW)
    source = yaml.safe_load((EVIDENCE / 'run-1/library/probe.yaml').read_text())
    assert dict(r.pin_mapping) == source['pinout']
    assert r.name == source['name']
    assert r.footprint_reference == 'probe:Resistor_PROBERESISTOR'
    assert r.raw_sha256 == hashlib.sha256(RAW).hexdigest()
    assert r.body_sha256 == hashlib.sha256(RAW.split(b'\n', 1)[1]).hexdigest()


def test_actual_repeat_keeps_date_and_raw_identity_separate():
    a = decode_probe_symbol(RAW)
    b = decode_probe_symbol((EVIDENCE / 'run-2/kicad/probe.lib').read_bytes())
    assert a.pin_mapping == b.pin_mapping and a.body_sha256 == b.body_sha256
    assert a.raw_date != b.raw_date and a.raw_sha256 != b.raw_sha256


@pytest.mark.parametrize(('old', 'new'), [
    (b'X L 1', b'X L 2'), (b'X R 2', b'X R 1'),
    (b'X L 1', b'X A 1'), (b' 1 1 P', b' 1 1 I'),
    (b'probe:Resistor_PROBERESISTOR', b'other:Resistor_PROBERESISTOR'),
    (b'DEF ProbeResistor', b'DEF Other'),
    (b'ENDDRAW', b'X Q 3 0 0 50 R 50 50 1 1 P\nENDDRAW'),
    (b'ENDDRAW', b'ENDDRAW\nENDDRAW'),
    (b'DRAW\n', b''), (b'ENDDEF', b''),
    (b'S -100 40 100 -40 1 1 12 f', b'S -101 40 100 -40 1 1 12 f'),
    (b'23/10/2026', b'31/02/2026'),
    (b'16:03:25', b'25:03:25'), (b'Version 2.3', b'Version 2.4'),
    (b'# End Library', b'# End Library\nunknown'),
    (b'#encoding utf-8', b'#encoding utf-8\x00'),
])
def test_mutations_fail_closed(old, new):
    with pytest.raises(ValueError):
        decode_probe_symbol(RAW.replace(old, new))


@pytest.mark.parametrize('raw', [b'', b'x'*16385, b'\xff', b'\x7f', RAW.replace(b'\n', b'\r')])
def test_resource_and_encoding_rejection(raw):
    with pytest.raises(ValueError):
        decode_probe_symbol(raw)


def test_crlf_and_horizontal_whitespace_are_not_hash_normalized():
    changed = RAW.replace(b'\n', b'\r\n').replace(b'X L 1 ', b'X\tL\t1 ')
    a, b = decode_probe_symbol(RAW), decode_probe_symbol(changed)
    assert a.pin_mapping == b.pin_mapping
    assert a.raw_sha256 != b.raw_sha256 and a.body_sha256 != b.body_sha256
