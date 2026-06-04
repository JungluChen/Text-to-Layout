from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "text-to-gds"


def _copytree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache"),
    )


def main() -> None:
    if not PLUGIN_ROOT.is_dir():
        raise SystemExit(f"Missing plugin root: {PLUGIN_ROOT}")

    shutil.copy2(ROOT / "pyproject.toml", PLUGIN_ROOT / "pyproject.toml")
    for filename in ["README.md", "TASKS.md", "AGENTS.md", "LICENSE", "CONTRIBUTING.md"]:
        source = ROOT / filename
        if source.is_file():
            shutil.copy2(source, PLUGIN_ROOT / filename)
    if (ROOT / "uv.lock").is_file():
        shutil.copy2(ROOT / "uv.lock", PLUGIN_ROOT / "uv.lock")
    for dirname in ["assets", "benchmarks", "docs", "scripts"]:
        source = ROOT / dirname
        if source.is_dir():
            _copytree(source, PLUGIN_ROOT / dirname)
    _copytree(ROOT / "src" / "text_to_gds", PLUGIN_ROOT / "src" / "text_to_gds")
    _copytree(ROOT / "skills" / "text-to-gds", PLUGIN_ROOT / "skills" / "text-to-gds")
    _copytree(ROOT / "examples", PLUGIN_ROOT / "examples")
    _copytree(ROOT / "drc", PLUGIN_ROOT / "drc")
    (PLUGIN_ROOT / "workspace" / "artifacts").mkdir(parents=True, exist_ok=True)
    (PLUGIN_ROOT / "workspace" / "artifacts" / ".gitkeep").touch()
    print(f"Bundled {PLUGIN_ROOT}")


if __name__ == "__main__":
    main()
