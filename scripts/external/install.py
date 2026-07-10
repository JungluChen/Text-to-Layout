"""Download pinned external source archives into .tools without vendoring them."""

from __future__ import annotations

import json

from _common import TOOLCHAIN_OUT, download_archive, load_registry, parser_with_tools, selected_tools, write_json


def main() -> int:
    parser = parser_with_tools(__doc__ or "")
    parser.add_argument("--all", action="store_true", help="download every registered archive")
    args = parser.parse_args()
    if not args.all and not args.tools:
        parser.error("pass --all or at least one --tool id")

    registry = load_registry()
    entries = []
    for tool in selected_tools(registry, args.tools):
        entries.append(download_archive(tool))
        print(f"downloaded {tool['id']}")
    payload = {
        "schema": "textlayout.external-tools.install-log.v1",
        "mode": "source_archive_cache_only",
        "entries": entries,
        "note": "Downloaded source archives are not solver execution evidence.",
    }
    write_json(TOOLCHAIN_OUT / "install_log.json", payload)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
