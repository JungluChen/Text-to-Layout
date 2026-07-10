"""Remove selected external source-cache archives from .tools."""

from __future__ import annotations

from pathlib import Path

from _common import ROOT, load_registry, parser_with_tools, selected_tools, source_archive_path


def _within_tools(path: Path) -> bool:
    resolved = path.resolve()
    tools = (ROOT / ".tools").resolve()
    return resolved == tools or tools in resolved.parents


def main() -> int:
    parser = parser_with_tools(__doc__ or "")
    parser.add_argument("--all", action="store_true", help="remove every registered source archive")
    args = parser.parse_args()
    if not args.all and not args.tools:
        parser.error("pass --all or at least one --tool id")

    registry = load_registry()
    for tool in selected_tools(registry, None if args.all else args.tools):
        archive = source_archive_path(tool)
        if not _within_tools(archive):
            raise RuntimeError(f"refusing to remove path outside .tools: {archive}")
        archive.unlink(missing_ok=True)
        print(f"removed {archive.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
