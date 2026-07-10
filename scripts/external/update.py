"""Inspect upstream refs for registry updates without mutating lock files."""

from __future__ import annotations

import subprocess

from _common import load_registry, parser_with_tools, selected_tools


def main() -> int:
    parser = parser_with_tools(__doc__ or "")
    args = parser.parse_args()
    registry = load_registry()
    for tool in selected_tools(registry, args.tools):
        repo = str(tool["upstream_repository"])
        ref = str(tool["pinned_ref"])
        completed = subprocess.run(
            ["git", "ls-remote", repo, ref, f"refs/tags/{ref}", f"refs/heads/{ref}"],
            capture_output=True,
            text=True,
            check=False,
        )
        print(f"{tool['id']}: pinned {ref} -> {tool['pinned_commit']}")
        if completed.returncode == 0 and completed.stdout.strip():
            print(completed.stdout.strip())
        else:
            print("  no exact upstream ref found; pinned commit remains authoritative")
    print("No files were changed. Update registry.toml and lock.toml deliberately after review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
