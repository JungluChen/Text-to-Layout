import json
from pathlib import Path

import pytest

from textlayout.external.qeda_inventory import compare_inventories, decode_inventory

ROOT = Path(__file__).resolve().parents[2]
ENTRY = {'path': 'node_modules/qeda/package.json', 'sha256': 'a' * 64}


def encode(rows):
    return json.dumps(rows).encode()


def test_reports_all_discrepancy_categories():
    expected = encode([ENTRY, {'path': 'lost', 'sha256': 'b' * 64}])
    observed = encode([dict(ENTRY, sha256='c' * 64), {'path': 'extra', 'sha256': 'd' * 64}])
    result = compare_inventories(expected, observed)
    assert result.missing == ('lost',)
    assert result.added == ('extra',)
    assert result.changed == (ENTRY['path'],)
    assert not result.matches_supplied_inventory


def test_audited_tree_and_retained_missing_file_case():
    raw = (ROOT / 'docs/progress/evidence/2026-10-26-102228/runtime-before.json').read_bytes()
    rows = json.loads(raw)
    drift = json.loads((ROOT / 'docs/progress/evidence/2026-10-27-223410/first.json').read_bytes())
    changed = encode([row for row in rows if row['path'] not in drift['missing']])
    assert compare_inventories(raw, changed).missing == tuple(drift['missing'])
    reversed_raw = encode(list(reversed(rows)))
    result = compare_inventories(raw, reversed_raw)
    assert result.matches_supplied_inventory
    assert result.expected_sha256 != result.observed_sha256
    assert len(decode_inventory(raw)) == 1084


@pytest.mark.parametrize('row', [
    {}, {'path': 'x'}, dict(ENTRY, extra=1), dict(ENTRY, symlink='target'),
    dict(ENTRY, sha256='A' * 64), dict(ENTRY, sha256=123),
    dict(ENTRY, path='../x'), dict(ENTRY, path='/x'), dict(ENTRY, path='a//b'),
    dict(ENTRY, path='a/./b'), dict(ENTRY, path='a\\b'), dict(ENTRY, path='C:x'),
    dict(ENTRY, path='a\nx'), {'path': 'x', 'symlink': '../outside'},
    {'path': 'x', 'symlink': '/outside'}, {'path': 'x', 'symlink': 'a/../../out'},
])
def test_rejects_ambiguous_or_escaping_records(row):
    with pytest.raises(ValueError):
        decode_inventory(encode([row]))


def test_duplicate_keys_and_paths_rejected():
    with pytest.raises(ValueError):
        decode_inventory(b'[{"path":"a","path":"b","symlink":"c"}]')
    with pytest.raises(ValueError):
        decode_inventory(encode([ENTRY, ENTRY]))


def test_missing_observed_tree_is_not_a_match():
    assert compare_inventories(encode([ENTRY]), b'[]').missing == (ENTRY['path'],)
    with pytest.raises(ValueError):
        compare_inventories(b'[]', b'[]')


def test_symlink_type_and_target_change_are_reported():
    first = encode([{'path': 'node_modules/.bin/qeda', 'symlink': '../qeda/bin/qeda'}])
    assert decode_inventory(first)[0].symlink == '../qeda/bin/qeda'
    second = encode([{'path': 'node_modules/.bin/qeda', 'sha256': 'a' * 64}])
    assert compare_inventories(first, second).changed == ('node_modules/.bin/qeda',)


@pytest.mark.parametrize('raw', [b'{}', b'null', b'\xff', b'[' * 2000, b' ' * (2 * 1024**2 + 1)])
def test_rejects_invalid_or_oversized_json(raw):
    with pytest.raises(ValueError):
        decode_inventory(raw)
