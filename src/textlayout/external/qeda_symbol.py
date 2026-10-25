"""Closed, fixed-probe legacy symbol dialect; not a general KiCad reader."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime

_BODY = '''#encoding utf-8
#
# ProbeResistor
#
DEF ProbeResistor R 0 40 N N 1 L N
F0 "R" 0 70 50 H V C BNN
F1 "ProbeResistor" 0 -70 50 H V C TNN
F2 "probe:Resistor_PROBERESISTOR" 0 0 0 H I C CNN
$FPLIST
Resistor_PROBERESISTOR
$ENDFPLIST
DRAW
S -100 40 100 -40 1 1 12 f
X L 1 -150 0 50 R 50 50 1 1 P
X R 2 150 0 50 L 50 50 1 1 P
ENDDRAW
ENDDEF
# End Library'''
_EXPECTED = tuple(tuple(line.split()) for line in _BODY.splitlines())
_HEADER = re.compile(r'EESchema-LIBRARY Version 2\.3 Date: ([0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2})\Z')


@dataclass(frozen=True)
class ProbeSymbol:
    name: str
    footprint_reference: str
    pin_mapping: tuple[tuple[str, int], ...]
    raw_date: str  # upstream local timestamp: timezone not asserted
    raw_sha256: str
    body_sha256: str  # raw bytes after first LF; never normalized


def decode_probe_symbol(data: bytes) -> ProbeSymbol:
    """Check every record of the audited ProbeResistor symbol template.

    Exact body tokens and order required, including L1/R2 passive pins and
    footprint association. Horizontal whitespace and LF/CRLF may vary; date must
    be calendar-valid. All bytes retained by hashes; date has unknown timezone.
    This is a narrow identity/template check, not independent symbol geometry,
    native import, generator execution, or electrical acceptance.
    """
    if len(data) > 16384:
        raise ValueError('symbol exceeds byte limit')
    try:
        text = data.decode('ascii')
    except UnicodeDecodeError as exc:
        raise ValueError('unsupported symbol encoding') from exc
    if any(ord(c) < 32 and c not in '\r\n\t' or ord(c) == 127 for c in text):
        raise ValueError('unsupported symbol control character')
    if '\r' in text.replace('\r\n', ''):
        raise ValueError('unsupported line ending')
    lines = text.splitlines()
    if not lines:
        raise ValueError('missing symbol header')
    match = _HEADER.fullmatch(lines[0])
    if match is None:
        raise ValueError('unsupported symbol header')
    raw_date = match.group(1)
    datetime.strptime(raw_date, '%d/%m/%Y %H:%M:%S')
    if tuple(tuple(line.split()) for line in lines[1:]) != _EXPECTED:
        raise ValueError('symbol identity, pin mapping or template mismatch')
    return ProbeSymbol(
        name='ProbeResistor', footprint_reference='probe:Resistor_PROBERESISTOR',
        pin_mapping=(('L', 1), ('R', 2)), raw_date=raw_date,
        raw_sha256=hashlib.sha256(data).hexdigest(),
        body_sha256=hashlib.sha256(data.split(b'\n', 1)[1]).hexdigest(),
    )
