"""Contracts for the idempotent WSL2 bootstrap entry point."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "bootstrap_wsl.sh"


def test_wsl_bootstrap_is_non_destructive_and_runs_the_supported_core_flow() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "rm -rf" not in text
    assert "/proc/sys/fs/binfmt_misc/WSLInterop" in text
    assert "WSL_DISTRO_NAME" in text
    assert '"/mnt/"' in text
    assert "TEXTLAYOUT_WSL_NATIVE_ROOT" in text
    assert "uv sync --frozen --dev" in text
    assert "uv run textlayout doctor" in text
    assert "uv run textlayout prompt" in text
    assert "uv run textlayout verify" in text
    assert "uv run pytest" in text


@pytest.mark.skipif(os.name == "nt", reason="requires a POSIX shell")
def test_wsl_bootstrap_dry_run_is_repeatable_and_has_no_side_effects(tmp_path: Path) -> None:
    env = os.environ | {"TEXTLAYOUT_WSL_NATIVE_ROOT": str(tmp_path / "native")}
    command = ["bash", str(SCRIPT), "--dry-run"]

    first = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    second = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=False)

    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert not (tmp_path / "native").exists()
