from pathlib import Path

import pytest

from textlayout.external.qeda_syntax import (
    MAX_ATOM_CHARS, MAX_BYTES, MAX_DEPTH, MAX_NODES,
    Atom, Expression, parse_footprint_syntax,
)

EVIDENCE = Path(__file__).resolve().parents[2] / 'docs/progress/evidence/2026-10-23-220348'


def test_retained_output_and_quote_counterexample():
    tree = parse_footprint_syntax((EVIDENCE / 'baseline.kicad_mod').read_bytes())
    assert tree.children[:2] == (Atom('module'), Atom('Resistor_PROBERESISTOR'))
    with pytest.raises(ValueError, match='control character in atom'):
        parse_footprint_syntax((EVIDENCE / 'unclosed_quote.kicad_mod').read_bytes())


@pytest.mark.parametrize('name', ['extra_copper', 'backside_module', 'pad_drill'])
def test_syntax_success_is_not_geometry_acceptance(name):
    # These require semantic rejection by the forthcoming assessment.
    assert isinstance(parse_footprint_syntax((EVIDENCE / f'{name}.kicad_mod').read_bytes()), Expression)


def test_quotes_and_nested_immutable_tree():
    assert parse_footprint_syntax(b'(m "a (b) \\" c\\\\" (1 "1"))') == Expression((
        Atom('m'), Atom('a (b) " c\\', True), Expression((Atom('1'), Atom('1', True))),
    ))


@pytest.mark.parametrize('data', [
    b'', b'x', b'(', b')', b'()()', b'()x', b'(x))', b'(x "oops)',
    b'(a"b")', b'("a"b)', b'("a""b")', b'(a\\b)', b'("a\\n")',
    b'(\xff)', b'(a\x00)', b'("a\n")', b'(a\x7f)', '(a\u00a0b)'.encode(),
])
def test_malformed_rejected(data):
    with pytest.raises(ValueError):
        parse_footprint_syntax(data)


def test_resource_boundaries():
    assert parse_footprint_syntax(b'(' * MAX_DEPTH + b')' * MAX_DEPTH)
    assert parse_footprint_syntax(b'(' + b'x' * MAX_ATOM_CHARS + b')')
    assert parse_footprint_syntax(b'(' + b'x ' * (MAX_NODES - 1) + b')')
    assert parse_footprint_syntax(b'()' + b' ' * (MAX_BYTES - 2))
    for data in [b' ' * (MAX_BYTES + 1), b'(' * (MAX_DEPTH + 1),
                 b'(' + b'x' * (MAX_ATOM_CHARS + 1) + b')',
                 b'(' + b'x ' * MAX_NODES + b')']:
        with pytest.raises(ValueError, match='limit'):
            parse_footprint_syntax(data)
