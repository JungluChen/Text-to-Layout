"""Strict comparison of supplied runtime inventories; no filesystem discovery."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

_SHA = re.compile(r'[0-9a-f]{64}\Z')


@dataclass(frozen=True)
class InventoryEntry:
    path: str
    sha256: str | None = None
    symlink: str | None = None


@dataclass(frozen=True)
class InventoryComparison:
    expected_sha256: str
    observed_sha256: str
    missing: tuple[str, ...]
    added: tuple[str, ...]
    changed: tuple[str, ...]
    matches_supplied_inventory: bool


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _path(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise ValueError('invalid inventory path')
    if any(ord(c) < 32 or ord(c) == 127 or c in '\\:' for c in value):
        raise ValueError('unsupported path character')
    if any(part in ('', '.', '..') for part in value.split('/')):
        raise ValueError('inventory path must be normalized and relative')
    return value


def decode_inventory(data: bytes) -> tuple[InventoryEntry, ...]:
    """Decode at most 2MiB/20000 entries; reject ambiguous records and paths.

    Each entry has path and exactly one lowercase SHA256 or relative symlink.
    Link targets may use .. within the inventory root, never escape it. No
    link is followed, no file opened, and no supplied hash is independently verified.
    """
    if len(data) > 2 * 1024**2:
        raise ValueError('inventory exceeds byte limit')
    try:
        payload = json.loads(data.decode('utf-8'), object_pairs_hook=_object)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('invalid inventory JSON') from exc
    if not isinstance(payload, list) or len(payload) > 20000:
        raise ValueError('inventory must be a bounded list')
    result: dict[str, InventoryEntry] = {}
    for row in payload:
        if not isinstance(row, dict) or set(row) not in ({'path', 'sha256'}, {'path', 'symlink'}):
            raise ValueError('unsupported inventory record')
        path = _path(row['path'])
        if path in result:
            raise ValueError('duplicate inventory path')
        if 'sha256' in row:
            digest = row['sha256']
            if not isinstance(digest, str) or _SHA.fullmatch(digest) is None:
                raise ValueError('invalid SHA256')
            result[path] = InventoryEntry(path, sha256=digest)
        else:
            target = row['symlink']
            if not isinstance(target, str) or not target or len(target) > 4096:
                raise ValueError('invalid symlink target')
            if target.startswith('/') or any(ord(c) < 32 or ord(c) == 127 or c in '\\:' for c in target):
                raise ValueError('unsupported symlink target')
            depth = len(path.split('/')) - 1
            for part in target.split('/'):
                if part in ('', '.'):
                    raise ValueError('unnormalized symlink target')
                depth += -1 if part == '..' else 1
                if depth < 0:
                    raise ValueError('symlink escapes inventory root')
            result[path] = InventoryEntry(path, symlink=target)
    return tuple(result[key] for key in sorted(result))


def compare_inventories(expected: bytes, observed: bytes) -> InventoryComparison:
    """Compare validated snapshots, not installations or numerical evidence.

    Expected inventory must be nonempty. Entry order/JSON whitespace do not
    affect comparison; both raw-byte hashes preserve that provenance difference.
    The caller must establish the expected snapshot's authority and freshness.
    """
    left = {entry.path: entry for entry in decode_inventory(expected)}
    right = {entry.path: entry for entry in decode_inventory(observed)}
    if not left:
        raise ValueError('expected inventory must not be empty')
    missing = tuple(sorted(left.keys() - right.keys()))
    added = tuple(sorted(right.keys() - left.keys()))
    changed = tuple(sorted(key for key in left.keys() & right.keys() if left[key] != right[key]))
    return InventoryComparison(
        hashlib.sha256(expected).hexdigest(), hashlib.sha256(observed).hexdigest(),
        missing, added, changed, not (missing or added or changed),
    )
