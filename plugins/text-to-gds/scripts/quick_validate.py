from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_ROOT_FILES = [
    "pyproject.toml",
    "README.md",
    "TASKS.md",
    "AGENTS.md",
    "src/text_to_gds/server.py",
    "src/text_to_gds/adapters.py",
    "skills/text-to-gds/SKILL.md",
    "skills/text-to-gds-circuit-design/SKILL.md",
    "skills/text-to-gds-layout-design/SKILL.md",
    "skills/text-to-gds-simulation/SKILL.md",
    "skills/text-to-gds-signoff/SKILL.md",
    "skills/text-to-gds/scripts/text_to_gds_tool.py",
]

REQUIRED_BUNDLE_FILES = [
    "pyproject.toml",
    "README.md",
    "src/text_to_gds/server.py",
    "src/text_to_gds/adapters.py",
    "skills/text-to-gds/SKILL.md",
    "skills/text-to-gds-circuit-design/SKILL.md",
    "skills/text-to-gds-layout-design/SKILL.md",
    "skills/text-to-gds-simulation/SKILL.md",
    "skills/text-to-gds-signoff/SKILL.md",
]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid JSON at {path}: {error}") from error
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return payload


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"Missing required file: {path}")


def _require_dir(path: Path) -> None:
    if not path.is_dir():
        raise SystemExit(f"Missing required directory: {path}")


def _reject_todo_placeholders(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "[TODO:" in text or "TODO:" in text:
        raise SystemExit(f"Metadata contains TODO placeholder: {path}")


def _validate_marketplace(root: Path, marketplace_dir: Path) -> list[Path]:
    marketplace_path = marketplace_dir / "marketplace.json"
    _require_file(marketplace_path)
    marketplace = _load_json(marketplace_path)
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        raise SystemExit(f"Marketplace must contain at least one plugin: {marketplace_path}")

    bundle_paths: list[Path] = []
    for index, plugin in enumerate(plugins):
        if not isinstance(plugin, dict):
            raise SystemExit(f"Marketplace plugin entry {index} must be an object")
        for key in ("name", "source", "policy", "category"):
            if key not in plugin:
                raise SystemExit(f"Marketplace plugin entry {index} missing {key}")
        source = plugin["source"]
        policy = plugin["policy"]
        if not isinstance(source, dict) or source.get("source") != "local" or "path" not in source:
            raise SystemExit(f"Marketplace plugin entry {index} must use a local source path")
        if not isinstance(policy, dict):
            raise SystemExit(f"Marketplace plugin entry {index} policy must be an object")
        if policy.get("installation") not in {"AVAILABLE", "INSTALLED_BY_DEFAULT", "NOT_AVAILABLE"}:
            raise SystemExit(f"Marketplace plugin entry {index} has invalid installation policy")
        if policy.get("authentication") not in {"ON_INSTALL", "ON_USE"}:
            raise SystemExit(f"Marketplace plugin entry {index} has invalid authentication policy")

        source_path = Path(str(source["path"]))
        bundle_path = (root / source_path).resolve()
        _require_dir(bundle_path)
        bundle_paths.append(bundle_path)

    _reject_todo_placeholders(marketplace_path)
    return bundle_paths


def validate(root: Path, marketplace_dir: Path) -> None:
    root = root.resolve()
    marketplace_dir = marketplace_dir.resolve()
    _require_dir(root)
    _require_dir(marketplace_dir)

    for relative_path in REQUIRED_ROOT_FILES:
        _require_file(root / relative_path)

    bundle_paths = _validate_marketplace(root, marketplace_dir)
    for bundle_path in bundle_paths:
        for relative_path in REQUIRED_BUNDLE_FILES:
            _require_file(bundle_path / relative_path)
        for metadata_dir in (bundle_path / ".codex-plugin", bundle_path / ".claude-plugin"):
            if metadata_dir.is_dir():
                for json_path in metadata_dir.glob("*.json"):
                    _load_json(json_path)
                    _reject_todo_placeholders(json_path)

    claude_marketplace = root / ".claude-plugin" / "marketplace.json"
    if claude_marketplace.exists():
        _load_json(claude_marketplace)
        _reject_todo_placeholders(claude_marketplace)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the Text-to-GDS plugin scaffold.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--plugin", type=Path, default=Path(".codex-plugin"))
    args = parser.parse_args()

    validate(args.root, args.plugin)
    print("Text-to-GDS scaffold validation passed")


if __name__ == "__main__":
    main()
