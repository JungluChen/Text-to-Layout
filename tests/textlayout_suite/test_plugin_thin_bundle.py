"""`plugins/text-to-gds` is metadata, never a second copy of the implementation.

The bundle once held 315 byte-identical copies of `src/text_to_gds`, a full
`src/textlayout`, the docs, the examples and a `uv.lock`. Nothing read them: the
plugin's `.mcp.json` launches the `text-to-gds` console script, which resolves
from the installed distribution. The copies only created a second place for a
fix to be forgotten.

These tests fail the moment an implementation file reappears in the bundle.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "text-to-gds"
SCRIPTS_DIR = REPO_ROOT / "scripts"

#: Caches are never committed, and are not the bundle's business.
_TRANSIENT = {"__pycache__", ".ruff_cache", ".pytest_cache"}


def _bundler():
    spec = importlib.util.spec_from_file_location(
        "bundle_plugin", SCRIPTS_DIR / "bundle_plugin.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bundle_plugin"] = module
    spec.loader.exec_module(module)
    return module


def _bundled_files() -> list[Path]:
    if not PLUGIN_ROOT.is_dir():
        return []
    return [
        path.relative_to(PLUGIN_ROOT)
        for path in PLUGIN_ROOT.rglob("*")
        if path.is_file() and not _TRANSIENT & set(path.relative_to(PLUGIN_ROOT).parts)
    ]


@pytest.fixture(scope="module")
def bundler():
    return _bundler()


class TestNoCopiedImplementation:
    def test_the_bundle_vendors_no_source_tree(self) -> None:
        for package in ("src", "text_to_gds", "textlayout"):
            assert not (PLUGIN_ROOT / package).exists(), (
                f"{package!r} reappeared in the plugin bundle; the plugin must depend on "
                "the released text-to-gds distribution, not vendor it"
            )

    def test_no_core_module_is_duplicated_in_the_bundle(self) -> None:
        """Not one file of the implementation may exist under two paths."""
        duplicated = [
            relative
            for relative in _bundled_files()
            if (REPO_ROOT / "src" / relative).is_file()
        ]
        assert duplicated == [], f"copied core implementation files: {duplicated}"

    def test_the_only_python_in_the_bundle_belongs_to_a_skill(self) -> None:
        """Skills legitimately ship helper scripts; nothing else may ship .py."""
        offenders = [
            relative
            for relative in _bundled_files()
            if relative.suffix == ".py" and relative.parts[0] != "skills"
        ]
        assert offenders == [], f"python outside skills/ in the plugin bundle: {offenders}"

    def test_every_bundled_path_is_allowlisted(self, bundler) -> None:
        strays = [str(p) for p in bundler._stray_paths()]
        assert strays == [], f"paths outside BUNDLE_ALLOWLIST: {strays}"

    def test_the_bundle_stays_small(self) -> None:
        """A guard on intent: metadata is tens of files, an implementation is hundreds."""
        assert len(_bundled_files()) < 100


class TestBundleIsInstallableMetadata:
    def _plugin_pyproject(self) -> dict:
        return tomllib.loads((PLUGIN_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    def _project_version(self) -> str:
        data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        return str(data["project"]["version"])

    def test_the_plugin_depends_on_the_released_distribution(self) -> None:
        dependencies = self._plugin_pyproject()["project"]["dependencies"]
        assert dependencies == [f"text-to-gds=={self._project_version()}"]

    def test_the_plugin_does_not_redeclare_the_core_package(self) -> None:
        """A bundle named `text-to-gds` would shadow the real distribution."""
        assert self._plugin_pyproject()["project"]["name"] == "text-to-gds-plugin"

    @pytest.mark.parametrize(
        "manifest", [".claude-plugin/plugin.json", ".codex-plugin/plugin.json"]
    )
    def test_manifest_version_tracks_the_project_version(self, manifest: str) -> None:
        """These had drifted to 0.1.0, 0.2.0 and 0.3.0 for one artifact."""
        payload = json.loads((PLUGIN_ROOT / manifest).read_text(encoding="utf-8"))
        assert payload["version"] == self._project_version()

    def test_version_file_tracks_the_project_version(self) -> None:
        recorded = (PLUGIN_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        assert recorded == self._project_version()

    def test_the_mcp_server_launches_the_installed_console_script(self) -> None:
        """This is *why* the bundle needs no source."""
        config = json.loads((PLUGIN_ROOT / ".mcp.json").read_text(encoding="utf-8"))
        assert "text-to-gds" in config["mcpServers"]["text-to-gds"]["args"]

    def test_skills_are_bundled(self) -> None:
        skills = list((PLUGIN_ROOT / "skills").glob("*/SKILL.md"))
        assert len(skills) >= 5


class TestBundleCheckGate:
    def test_check_passes_on_the_committed_bundle(self, bundler) -> None:
        assert bundler.check() == 0

    def test_check_rejects_a_smuggled_implementation_file(
        self, bundler, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        """The gate must catch a re-vendored core module, not just a stale one."""
        fake_plugin = tmp_path / "plugins" / "text-to-gds"
        (fake_plugin / "src" / "textlayout").mkdir(parents=True)
        (fake_plugin / "src" / "textlayout" / "cli.py").write_text("# copied", encoding="utf-8")
        monkeypatch.setattr(bundler, "PLUGIN_ROOT", fake_plugin)

        assert bundler.check() == 1
        assert "copied implementation file" in capsys.readouterr().err
