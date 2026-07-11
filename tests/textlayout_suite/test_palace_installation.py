from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "external"


def _load(name: str):
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_spack_environment_requests_exact_palace_release() -> None:
    text = (ROOT / "external_tools" / "palace" / "spack.yaml").read_text(encoding="utf-8")
    assert "palace@0.17.0" in text
    assert "+arpack" in text
    assert "+superlu-dist" in text


def test_installer_keeps_pinned_sources_and_identity_under_ignored_tools_tree() -> None:
    """The auditable artifacts stay under .tools/; the Spack build tree is native.

    The pinned source archives (verified by SHA-256) and the small install
    identity record live under the git-ignored .tools/ tree. The Spack clone,
    caches, build stage, and installed binaries are placed on native WSL ext4
    for viable performance (the /mnt/c 9p mount stalls the FEM-stack install);
    those binaries are still git-ignored, never committed, and never in src/.
    """
    common = _load("_palace_common")
    # Pinned source archives and the install-identity record stay under .tools/.
    assert common.PALACE_ROOT == common.ROOT / ".tools" / "palace"
    assert common.INSTALL_RECORD == common.PALACE_ROOT / "install.json"
    assert (
        common.palace_archive().resolve().is_relative_to(
            (common.ROOT / ".tools" / "external" / "sources").resolve()
        )
    )
    # The Spack tree is resolved to a native path, overridable and documented.
    installer = _load("install_palace")
    source = (SCRIPTS / "install_palace.py").read_text(encoding="utf-8")
    assert "TEXTLAYOUT_PALACE_NATIVE_ROOT" in source
    assert ".cache/textlayout-palace" in source
    assert callable(installer._native_root)


def test_installer_reuses_a_verified_installation(monkeypatch, tmp_path: Path) -> None:
    installer = _load("install_palace")
    existing = {
        "status": "INSTALLED",
        "palace_version": "0.17.0",
        "palace_executable": "wsl:/opt/palace/bin/palace",
        "palace_executable_sha256": "a" * 64,
    }
    monkeypatch.setattr(installer, "download_archive", lambda tool: {})
    monkeypatch.setattr(installer, "gmsh_identity", lambda: {"version": "4.15.2"})
    monkeypatch.setattr(
        installer,
        "verify_palace_archive",
        lambda: {
            "available": True,
            "sha256": "169f7fe210ea6e771a29bfe0803dd84a774b25b00d2aa3a1f33b9d97a510ff9d",
        },
    )
    monkeypatch.setattr(installer, "palace_install_identity", lambda: existing)
    monkeypatch.setattr(
        installer,
        "_spack_install",
        lambda: (_ for _ in ()).throw(AssertionError("valid install must be reused")),
    )
    monkeypatch.setattr(installer, "INSTALL_RECORD", tmp_path / "install.json")
    monkeypatch.setattr(installer, "INSTALL_REPORT", tmp_path / "report.json")
    monkeypatch.setattr(sys, "argv", ["install_palace.py"])
    assert installer.main() == 0
    assert '"reused": true' in (tmp_path / "report.json").read_text(encoding="utf-8")


def test_capability_can_use_verified_install_manifest(monkeypatch, tmp_path: Path) -> None:
    from textlayout.solvers.palace import capability

    record = tmp_path / "install.json"
    record.write_text(
        '{"palace_executable":"wsl:/opt/palace/bin/palace"}', encoding="utf-8"
    )
    monkeypatch.setattr(capability, "_INSTALL_RECORD", record)
    monkeypatch.setattr(
        capability,
        "find_executable",
        lambda names, explicit=None, **kwargs: explicit,
    )
    monkeypatch.setattr(capability, "_probe_executable_version", lambda executable: "0.17.0")
    monkeypatch.setattr(capability, "_hash_executable", lambda executable: "b" * 64)
    detected = capability.detect_palace()
    assert detected.available is True
    assert detected.version == "0.17.0"
    assert detected.executable_sha256 == "b" * 64
