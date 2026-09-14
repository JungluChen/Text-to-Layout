"""Executable paths must survive switching into a solver working directory."""

import os
from pathlib import Path

import pytest

from textlayout.simulation.runners import find_executable


def test_explicit_relative_path_is_resolved(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    executable = Path("solver")
    executable.write_bytes(b"#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    assert find_executable(("solver",), "./solver") == str(executable.resolve())


@pytest.mark.skipif(os.name == "nt", reason="native Unix binary discovery")
def test_native_elf_is_not_sent_to_wsl(tmp_path):
    executable = tmp_path / "solver"
    executable.write_bytes(b"\x7fELF")
    executable.chmod(0o755)
    assert find_executable(("solver",), str(executable)) == str(executable)
