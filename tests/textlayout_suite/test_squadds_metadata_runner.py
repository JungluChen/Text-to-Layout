import json
import sys
from pathlib import Path

import pytest

from textlayout.external.squadds_metadata_runner import run_metadata

SOURCE = Path(__file__).resolve().parents[2] / 'docs/progress/evidence/2026-10-17-144536/local-packet/source/measured_device_database.json'


def test_missing_interpreter_retains_failure(tmp_path: Path) -> None:
    out = tmp_path / 'run'
    result = run_metadata(SOURCE, python=tmp_path / 'missing', output_dir=out)
    assert result.assessment is None and result.failure_reason
    assert result.return_code is None
    manifest = json.loads((out / 'manifest.json').read_text())
    assert {'database.json', 'result.json', 'stdout.txt', 'stderr.txt'} <= set(manifest['artifact_sha256'])
    assert manifest['physics_verified'] is False


def test_existing_directory_refused(tmp_path: Path) -> None:
    with pytest.raises(FileExistsError):
        run_metadata(SOURCE, python=Path(sys.executable), output_dir=tmp_path)
    assert not list(tmp_path.iterdir())


def test_changed_input_refused_before_output(tmp_path: Path) -> None:
    source = tmp_path / 'bad.json'
    source.write_bytes(b'[]')
    with pytest.raises(ValueError, match='pinned'):
        run_metadata(source, python=Path(sys.executable), output_dir=tmp_path / 'run')
    assert not (tmp_path / 'run').exists()


def test_real_child_timeout_retains_logs(tmp_path: Path) -> None:
    result = run_metadata(SOURCE, python=Path(sys.executable), output_dir=tmp_path / 'run', timeout_seconds=1e-9)
    assert result.assessment is None and 'timed out' in str(result.failure_reason)
    assert (tmp_path / 'run' / 'stderr.txt').exists()
