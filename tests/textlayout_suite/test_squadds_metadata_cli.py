import json
from pathlib import Path

import pytest

from textlayout.cli import main

SOURCE = Path(__file__).resolve().parents[2] / 'docs/progress/evidence/2026-10-17-144536/local-packet/source/measured_device_database.json'


def test_cli_missing_interpreter_is_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(['squadds-metadata', str(SOURCE), '--python', str(tmp_path / 'missing'), '--out', str(tmp_path / 'run')])
    assert code == 1
    packet = json.loads(capsys.readouterr().out)
    assert packet['assessment'] is None and packet['failure_reason']


@pytest.mark.parametrize('timeout', ['nan', '0', '-1'])
def test_cli_invalid_timeout_no_output(tmp_path: Path, capsys: pytest.CaptureFixture[str], timeout: str) -> None:
    out = tmp_path / 'run'
    assert main(['squadds-metadata', str(SOURCE), '--python', 'missing', '--out', str(out), '--timeout', timeout]) == 1
    assert json.loads(capsys.readouterr().err)['error'] == 'ValueError'
    assert not out.exists()
