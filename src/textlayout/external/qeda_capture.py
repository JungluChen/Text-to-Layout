"""Bounded inventory capture for a trusted, quiescent runtime directory."""
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

from textlayout.external.qeda_inventory import decode_inventory

MAX_ENTRIES = 20000
MAX_DEPTH = 64
MAX_FILE_BYTES = 16 * 1024**2
MAX_TOTAL_BYTES = 256 * 1024**2
MAX_SNAPSHOT_BYTES = 2 * 1024**2


def _identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _reparse(info: os.stat_result) -> bool:
    return bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def capture_inventory(root: Path) -> bytes:
    """Capture node_modules below an explicit absolute runtime root.

    Root and its ancestors must be trusted and quiescent. Symlinks are recorded,
    never traversed; other reparse points and special files are rejected. Bounds
    include directories in entry count. Errors abort without a partial snapshot.
    Missing/unreadable paths propagate OSError; unsupported/oversized trees raise
    ValueError. This is not a sandbox or an atomic/concurrent-writer guarantee.
    No runtime is imported/executed and root package/lock/Node are excluded.
    """
    if not root.is_absolute():
        raise ValueError('runtime root must be absolute')
    for directory in (root, root / 'node_modules'):
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or _reparse(info):
            raise ValueError('runtime root and node_modules must be real directories')
    rows: list[dict[str, str]] = []
    pending = [(root / 'node_modules', 0)]
    entries = 0
    total_bytes = 0
    while pending:
        directory, depth = pending.pop()
        if depth > MAX_DEPTH:
            raise ValueError('inventory exceeds depth limit')
        with os.scandir(directory) as children:
            for child in children:
                entries += 1
                if entries > MAX_ENTRIES:
                    raise ValueError('inventory exceeds entry limit')
                path = Path(child.path)
                relative = path.relative_to(root).as_posix()
                before = child.stat(follow_symlinks=False)
                if stat.S_ISLNK(before.st_mode):
                    rows.append({'path': relative, 'symlink': os.readlink(path)})
                elif _reparse(before):
                    raise ValueError('unsupported reparse point')
                elif stat.S_ISDIR(before.st_mode):
                    pending.append((path, depth + 1))
                elif stat.S_ISREG(before.st_mode):
                    if before.st_size > MAX_FILE_BYTES:
                        raise ValueError('inventory file exceeds byte limit')
                    if total_bytes + before.st_size > MAX_TOTAL_BYTES:
                        raise ValueError('inventory exceeds total byte limit')
                    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0)
                    flags |= getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
                    fd = os.open(path, flags)
                    with os.fdopen(fd, 'rb') as stream:
                        opened = os.fstat(stream.fileno())
                        if not stat.S_ISREG(opened.st_mode) or _identity(opened) != _identity(before):
                            raise ValueError('inventory file changed before read')
                        digest = hashlib.sha256()
                        count = 0
                        while block := stream.read(min(65536, MAX_FILE_BYTES - count + 1)):
                            count += len(block)
                            total_bytes += len(block)
                            if count > MAX_FILE_BYTES or total_bytes > MAX_TOTAL_BYTES:
                                raise ValueError('inventory exceeds read byte limit')
                            digest.update(block)
                        if count != before.st_size or _identity(os.fstat(stream.fileno())) != _identity(before):
                            raise ValueError('inventory file changed during read')
                    if _identity(path.lstat()) != _identity(before):
                        raise ValueError('inventory file changed after read')
                    rows.append({'path': relative, 'sha256': digest.hexdigest()})
                else:
                    raise ValueError('unsupported special file')
                # Bound serialized output before retaining an unbounded snapshot.
                if len(relative) > 4096:
                    raise ValueError('inventory path exceeds limit')
    rows.sort(key=lambda row: row['path'])
    data = json.dumps(rows, sort_keys=True).encode()
    if len(data) > MAX_SNAPSHOT_BYTES:
        raise ValueError('inventory exceeds snapshot byte limit')
    decode_inventory(data)
    return data
