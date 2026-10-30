import os
from pathlib import Path

import pytest

from textlayout.external import qeda_root

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = b'{"name":"runtime","private":true,"dependencies":{"qeda":"0.4.1"}}\n'


def populate(root):
    (root / 'package.json').write_bytes(PACKAGE)
    # Retained JSON is represented with LF, including on Windows checkouts.
    lock = (ROOT / 'docs/progress/evidence/2026-10-22-220849/runtime-lock.json').read_bytes()
    (root / 'package-lock.json').write_bytes(lock.replace(b'\r\n', b'\n'))


def test_exact_audit_and_each_metadata_mismatch(tmp_path):
    populate(tmp_path)
    result = qeda_root.compare_root_metadata(tmp_path)
    assert result.matches_audited_metadata
    assert result == qeda_root.compare_root_metadata(tmp_path)
    for name in ['package.json', 'package-lock.json']:
        populate(tmp_path)
        path = tmp_path / name
        path.write_bytes(path.read_bytes() + b'\n')
        assert not qeda_root.compare_root_metadata(tmp_path).matches_audited_metadata


def test_missing_relative_and_nonregular(tmp_path):
    with pytest.raises(ValueError, match='absolute'):
        qeda_root.compare_root_metadata(Path('relative'))
    with pytest.raises(FileNotFoundError):
        qeda_root.compare_root_metadata(tmp_path)
    (tmp_path / 'package.json').mkdir()
    with pytest.raises(ValueError, match='regular'):
        qeda_root.compare_root_metadata(tmp_path)


def test_oversize_and_unreadable(tmp_path, monkeypatch):
    populate(tmp_path)
    monkeypatch.setattr(qeda_root, 'MAX_METADATA_BYTES', len(PACKAGE) - 1)
    with pytest.raises(ValueError, match='byte limit'):
        qeda_root.compare_root_metadata(tmp_path)
    monkeypatch.setattr(qeda_root, 'MAX_METADATA_BYTES', 1024 * 1024)
    def denied(*args):
        raise PermissionError('injected unreadable file')
    monkeypatch.setattr(qeda_root.os, 'open', denied)
    with pytest.raises(PermissionError):
        qeda_root.compare_root_metadata(tmp_path)


@pytest.mark.skipif(os.name == 'nt', reason='actual Windows link fixtures pending')
def test_links_rejected(tmp_path):
    populate(tmp_path)
    link = tmp_path / 'root-link'
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match='real directory'):
        qeda_root.compare_root_metadata(link)
    path = tmp_path / 'package.json'
    path.unlink()
    path.symlink_to(tmp_path / 'package-lock.json')
    with pytest.raises(ValueError, match='regular'):
        qeda_root.compare_root_metadata(tmp_path)


def test_replacement_before_open_rejected(tmp_path, monkeypatch):
    populate(tmp_path)
    original = os.open
    def replaced(path, flags):
        replacement = tmp_path / 'replacement'
        replacement.write_bytes(PACKAGE)
        replacement.replace(path)
        return original(path, flags)
    monkeypatch.setattr(qeda_root.os, 'open', replaced)
    with pytest.raises(ValueError, match='changed before'):
        qeda_root.compare_root_metadata(tmp_path)
