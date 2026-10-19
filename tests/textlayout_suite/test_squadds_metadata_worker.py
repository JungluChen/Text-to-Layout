"""Fail closed before optional imports; real runtime evidence is retained separately."""
from pathlib import Path

import pytest

from textlayout.external._squadds_metadata_worker import execute


def test_changed_data_rejected_before_optional_import(tmp_path: Path) -> None:
    database = tmp_path / "source.json"
    database.write_text("[]")
    output = tmp_path / "raw.json"
    with pytest.raises(ValueError, match="pinned WM1"):
        execute(database, output)
    assert not output.exists()


def test_existing_output_preserved(tmp_path: Path) -> None:
    output = tmp_path / "raw.json"
    output.write_text("original evidence")
    with pytest.raises(FileExistsError):
        execute(tmp_path / "absent.json", output)
    assert output.read_text() == "original evidence"
