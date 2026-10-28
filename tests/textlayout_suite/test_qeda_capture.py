import hashlib
import json
import os
from pathlib import Path

import pytest

from textlayout.external import qeda_capture as capture


def tree(tmp_path):
    modules = tmp_path / 'node_modules'
    modules.mkdir()
    (modules / 'z').write_bytes(b'payload')
    return tmp_path


def test_deterministic_regular_files_excluding_root_metadata(tmp_path):
    root = tree(tmp_path)
    (root / 'package.json').write_text('excluded')
    first = capture.capture_inventory(root)
    assert first == capture.capture_inventory(root)
    assert json.loads(first) == [{
        'path': 'node_modules/z', 'sha256': hashlib.sha256(b'payload').hexdigest(),
    }]


def test_missing_relative_and_non_directory_roots(tmp_path):
    with pytest.raises(ValueError):
        capture.capture_inventory(Path('relative'))
    with pytest.raises(FileNotFoundError):
        capture.capture_inventory(tmp_path)
    (tmp_path / 'node_modules').write_text('file')
    with pytest.raises(ValueError):
        capture.capture_inventory(tmp_path)


@pytest.mark.parametrize('limit,value', [
    ('MAX_ENTRIES', 0), ('MAX_FILE_BYTES', 1), ('MAX_TOTAL_BYTES', 1),
    ('MAX_SNAPSHOT_BYTES', 1),
])
def test_limits_fail_without_partial_snapshot(tmp_path, monkeypatch, limit, value):
    root = tree(tmp_path)
    monkeypatch.setattr(capture, limit, value)
    with pytest.raises(ValueError):
        capture.capture_inventory(root)


def test_depth_limit_counts_empty_directories(tmp_path, monkeypatch):
    root = tree(tmp_path)
    (root / 'node_modules' / 'deep').mkdir()
    monkeypatch.setattr(capture, 'MAX_DEPTH', 0)
    with pytest.raises(ValueError, match='depth'):
        capture.capture_inventory(root)


@pytest.mark.skipif(os.name == 'nt', reason='POSIX symlink/FIFO fixture; Windows reparse validation pending')
def test_links_recorded_not_followed_and_special_files_rejected(tmp_path):
    root = tree(tmp_path)
    modules = root / 'node_modules'
    (modules / 'link').symlink_to('z')
    assert json.loads(capture.capture_inventory(root))[0] == {
        'path': 'node_modules/link', 'symlink': 'z',
    }
    os.mkfifo(modules / 'fifo')
    with pytest.raises(ValueError, match='special'):
        capture.capture_inventory(root)


@pytest.mark.skipif(os.name == 'nt', reason='POSIX symlink fixture; Windows reparse validation pending')
def test_escaping_link_and_symlink_root_rejected(tmp_path):
    root = tree(tmp_path)
    (root / 'node_modules' / 'link').symlink_to('../../outside')
    with pytest.raises(ValueError, match='escapes'):
        capture.capture_inventory(root)
    alias = tmp_path / 'alias'
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError):
        capture.capture_inventory(alias)


def test_unreadable_file_aborts(tmp_path, monkeypatch):
    root = tree(tmp_path)

    def denied(*args, **kwargs):
        raise PermissionError('fixture denied')

    monkeypatch.setattr(capture.os, 'open', denied)
    with pytest.raises(PermissionError, match='fixture denied'):
        capture.capture_inventory(root)


@pytest.mark.skipif(os.name == 'nt', reason='POSIX directory symlink fixture')
def test_directory_link_is_recorded_without_recursion(tmp_path):
    root = tree(tmp_path)
    directory = root / 'node_modules' / 'sub'
    directory.mkdir()
    (directory / 'back').symlink_to('..', target_is_directory=True)
    rows = json.loads(capture.capture_inventory(root))
    assert len(rows) == 2
    assert {'path': 'node_modules/sub/back', 'symlink': '..'} in rows


def test_cached_directory_entry_identity_is_not_used(tmp_path, monkeypatch):
    root = tree(tmp_path)
    original = os.scandir

    class Entry:
        def __init__(self, entry):
            self.path = entry.path

        def stat(self, **kwargs):
            raise AssertionError('cached DirEntry identity is not portable')

    class Scan:
        def __init__(self, path):
            self.inner = original(path)

        def __enter__(self):
            return (Entry(entry) for entry in self.inner)

        def __exit__(self, *args):
            self.inner.close()

    monkeypatch.setattr(capture.os, 'scandir', Scan)
    assert len(json.loads(capture.capture_inventory(root))) == 1


def test_replacement_before_open_is_still_rejected(tmp_path, monkeypatch):
    root = tree(tmp_path)
    original = os.open

    def replace_then_open(path, flags):
        path.unlink()
        path.write_bytes(b'different size')
        return original(path, flags)

    monkeypatch.setattr(capture.os, 'open', replace_then_open)
    with pytest.raises(ValueError, match='changed before read'):
        capture.capture_inventory(root)
