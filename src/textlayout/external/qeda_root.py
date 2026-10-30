"""Verify root metadata against the retained QEDA reconstruction audit."""
from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from textlayout.external.qeda_capture import _identity, _path_matches_handle, _reparse

PACKAGE_SHA256 = 'c2f7b0bf023cdbedf93cdd4e38f5c341ef893e20118e7b9def23ce9e0820ec66'
LOCK_SHA256 = 'c5a36c6ae2f9b7c2b2f31f1a83c25b4f6e31c8987247e9fa001b8d6ee088a8b0'
MAX_METADATA_BYTES = 1024 * 1024


@dataclass(frozen=True)
class RootMetadataComparison:
    package_sha256: str
    lock_sha256: str

    @property
    def matches_audited_metadata(self) -> bool:
        return self.package_sha256 == PACKAGE_SHA256 and self.lock_sha256 == LOCK_SHA256


def _hash_metadata(path: Path) -> str:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or _reparse(before):
        raise ValueError('root metadata must be a regular non-reparse file')
    if before.st_size > MAX_METADATA_BYTES:
        raise ValueError('root metadata exceeds byte limit')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0)
    flags |= getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or not _path_matches_handle(before, opened):
            raise ValueError('root metadata changed before read')
        data = stream.read(MAX_METADATA_BYTES + 1)
        if len(data) > MAX_METADATA_BYTES:
            raise ValueError('root metadata exceeds read byte limit')
        if len(data) != before.st_size or _identity(os.fstat(stream.fileno())) != _identity(opened):
            raise ValueError('root metadata changed during read')
    if _identity(path.lstat()) != _identity(before):
        raise ValueError('root metadata changed after read')
    return hashlib.sha256(data).hexdigest()


def compare_root_metadata(root: Path) -> RootMetadataComparison:
    """Read package.json/package-lock.json from a trusted, quiescent absolute root.

    Reads at most 1 MiB + 1 per file; rejects links, reparse points, special files
    and observed mutations. Missing/unreadable files propagate OSError. Invalid
    paths/files raise ValueError. Different bytes (including whitespace) return
    a nonmatching comparison, not a JSON semantic equivalence verdict.
    Ancestors must be trusted. This is not atomic or execution-time integrity,
    publisher attestation, Node/node_modules verification or runtime readiness.
    No runtime execution, dependencies, writes or network operations.
    """
    if not root.is_absolute():
        raise ValueError('runtime root must be absolute')
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or _reparse(info):
        raise ValueError('runtime root must be a real directory')
    return RootMetadataComparison(
        _hash_metadata(root / 'package.json'),
        _hash_metadata(root / 'package-lock.json'),
    )
