"""Drift guard: every Palace toolchain source must agree on the same pins.

The pinned Palace/Gmsh toolchain is described in five places:

    external_tools/registry.toml            (registry of external tools)
    external_tools/palace/spack.yaml        (committed Spack environment)
    external_tools/palace/README.md         (human-facing boundary contract)
    scripts/external/_palace_common.py      (constants used by installer/checker/smoke)
    external_tools/palace/smoke/eigenmode/manifest.json (official smoke case)

If any of them drifts from the others, the installer can build one Palace
while the checker and the evidence pipeline claim another. This test fails
on any disagreement.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "external"

EXPECTED_PALACE_VERSION = "0.17.0"
EXPECTED_PALACE_COMMIT = "12d8069afb5aa9e169a17e303d735e120968e9f2"
EXPECTED_GMSH_VERSION = "4.15.2"


def _palace_common():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "_palace_common_pins", SCRIPTS / "_palace_common.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_palace_common_pins"] = module
    spec.loader.exec_module(module)
    return module


def _registry_palace() -> dict:
    registry = tomllib.loads(
        (ROOT / "external_tools" / "registry.toml").read_text(encoding="utf-8")
    )
    return next(tool for tool in registry["tools"] if tool["id"] == "palace")


def test_registry_and_scripts_agree_on_palace_pins() -> None:
    common = _palace_common()
    tool = _registry_palace()
    assert common.PALACE_VERSION == EXPECTED_PALACE_VERSION
    assert common.PALACE_COMMIT == EXPECTED_PALACE_COMMIT
    assert common.GMESH_VERSION == EXPECTED_GMSH_VERSION
    assert tool["pinned_ref"] == f"v{common.PALACE_VERSION}"
    assert tool["pinned_commit"] == common.PALACE_COMMIT
    assert tool["source_archive_sha256"] == common.PALACE_SOURCE_SHA256
    assert common.PALACE_COMMIT in tool["source_archive_url"]
    assert tool["spdx_license"] == "Apache-2.0"


def test_spack_environment_matches_pinned_version() -> None:
    common = _palace_common()
    text = (ROOT / "external_tools" / "palace" / "spack.yaml").read_text(encoding="utf-8")
    assert f"palace@{common.PALACE_VERSION}" in text


def test_palace_readme_states_the_pinned_toolchain() -> None:
    common = _palace_common()
    text = (ROOT / "external_tools" / "palace" / "README.md").read_text(encoding="utf-8")
    assert f"Palace {common.PALACE_VERSION}" in text
    assert common.GMESH_VERSION in text
    assert "WSL" in text
    assert "Spack" in text or "spack" in text
    assert ".tools/palace" in text


def test_smoke_manifest_pins_the_registry_commit() -> None:
    common = _palace_common()
    manifest = json.loads(
        (ROOT / "external_tools" / "palace" / "smoke" / "eigenmode" / "manifest.json")
        .read_text(encoding="utf-8")
    )
    assert manifest["palace_commit"] == common.PALACE_COMMIT


def test_toolchain_paths_are_the_documented_locations() -> None:
    common = _palace_common()
    assert common.PALACE_ROOT == ROOT / ".tools" / "palace"
    assert common.INSTALL_RECORD == common.PALACE_ROOT / "install.json"
    assert common.INSTALL_REPORT == ROOT / "out" / "toolchain" / "palace_install.json"
    assert common.CHECK_REPORT == ROOT / "out" / "toolchain" / "palace_check.json"
    assert common.SMOKE_ROOT == ROOT / "out" / "toolchain" / "palace_smoke"


def test_registry_documents_wsl_spack_strategy_and_outputs() -> None:
    tool = _registry_palace()
    assert "Windows via WSL" in tool["supported_operating_systems"]
    assert tool["expected_output_files"] == ["postpro/eig.csv", "postpro/domain-E.csv"]
    assert tool["redistribute_source"] is False
    assert tool["redistribute_binaries"] is False
