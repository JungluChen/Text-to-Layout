import hashlib
import json
from pathlib import Path

import pytest

from textlayout.external.qeda_prepare import prepare_probe

ROOT = Path(__file__).resolve().parents[2]


def test_prepares_audited_input_with_truthful_hashes(tmp_path: Path) -> None:
    runtime = tmp_path / 'missing runtime' / 'qeda'
    first = prepare_probe(tmp_path / 'first', runtime_package=runtime)
    second = prepare_probe(tmp_path / 'second', runtime_package=runtime)
    assert first.status == 'input_files_prepared'
    assert not runtime.exists()
    assert first.manifest_sha256 == second.manifest_sha256
    manifest = json.loads(first.manifest_path.read_bytes())
    assert manifest['runtime_identity_status'] == 'NOT_VERIFIED'
    assert manifest['execution_status'] == 'NOT_EXECUTED'
    assert manifest['reference_status'] == 'NOT_EVALUATED'
    assert hashlib.sha256(first.manifest_path.read_bytes()).hexdigest() == first.manifest_sha256
    for name, digest in manifest['input_hashes'].items():
        assert hashlib.sha256((first.output_dir / name).read_bytes()).hexdigest() == digest
    assert (first.output_dir / 'library/probe.yaml').read_bytes() == (
        ROOT / 'docs/progress/evidence/2026-10-23-160519/run-1/library/probe.yaml'
    ).read_bytes()
    assert not (first.output_dir / 'kicad').exists()
    assert len(manifest['expected_outputs']) == 4


def test_existing_directory_is_preserved(tmp_path: Path) -> None:
    output = tmp_path / 'existing'
    output.mkdir()
    marker = output / 'mine'
    marker.write_bytes(b'preserve')
    with pytest.raises(FileExistsError):
        prepare_probe(output, runtime_package=tmp_path / 'qeda')
    assert list(output.iterdir()) == [marker]
    assert marker.read_bytes() == b'preserve'


def test_existing_file_is_preserved(tmp_path: Path) -> None:
    output = tmp_path / 'existing'
    output.write_bytes(b'preserve')
    with pytest.raises(FileExistsError):
        prepare_probe(output, runtime_package=tmp_path / 'qeda')
    assert output.read_bytes() == b'preserve'


@pytest.mark.parametrize('runtime', ['qeda', 'relative/qeda', '/bad\npath', '/bad\x00path'])
def test_invalid_runtime_does_not_create_output(tmp_path: Path, runtime: str) -> None:
    output = tmp_path / 'new'
    with pytest.raises(ValueError):
        prepare_probe(output, runtime_package=Path(runtime))
    assert not output.exists()


def test_runtime_path_is_json_encoded(tmp_path: Path) -> None:
    runtime = tmp_path / "quote'\";throw Error('injection');\\qeda"
    result = prepare_probe(tmp_path / 'new', runtime_package=runtime)
    first_line = (result.output_dir / 'generate.cjs').read_text().splitlines()[0]
    assert json.loads(first_line.removeprefix('const Qeda = require(').removesuffix(');')) == str(runtime)


def test_missing_parent_is_not_created(tmp_path: Path) -> None:
    output = tmp_path / 'missing' / 'new'
    with pytest.raises(FileNotFoundError):
        prepare_probe(output, runtime_package=tmp_path / 'qeda')
    assert not output.parent.exists()
