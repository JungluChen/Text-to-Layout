from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXTERNAL = ROOT / "scripts" / "external"
if str(EXTERNAL) not in sys.path:
    sys.path.insert(0, str(EXTERNAL))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, EXTERNAL / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_paraview_registry_lock_and_scripts_are_pinned() -> None:
    registry = tomllib.loads((ROOT / "external_tools" / "registry.toml").read_text())
    lock = tomllib.loads((ROOT / "external_tools" / "lock.toml").read_text())
    tool = next(item for item in registry["tools"] if item["id"] == "paraview")
    locked = next(item for item in lock["locked_tools"] if item["id"] == "paraview")
    assert tool["pinned_ref"] == "v5.13.3"
    assert tool["pinned_commit"] == locked["resolved_commit"]
    assert tool["source_archive_sha256"] == locked["source_archive_sha256"]
    assert tool["binary_archive_sha256"] == locked["binary_archive_sha256"]
    assert tool["spdx_license"] == "BSD-3-Clause"
    scripts = ROOT / "external_tools" / "paraview"
    assert len(list(scripts.glob("render_*.py"))) == 6


def test_retained_paraview_smoke_hashes_verify_when_installed() -> None:
    checker = _load("check_paraview")
    payload = checker.check()
    if payload["identity"] is None:
        pytest.skip("pinned ParaView is optional")
    assert payload["state"] == "SMOKE_TEST_PASSED"
    result = json.loads(
        (ROOT / "out" / "toolchain" / "paraview_smoke" / "result.json").read_text()
    )
    assert result["return_code"] == 0
    assert len(result["output_sha256"]) == 64

