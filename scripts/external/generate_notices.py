"""Generate THIRD_PARTY_NOTICES.md from external_tools/registry.toml."""

from __future__ import annotations

from _common import NOTICES, load_registry


def render_notices() -> str:
    registry = load_registry()
    lines = [
        "# Third Party Notices",
        "",
        "This file is generated from `external_tools/registry.toml`.",
        "It records upstream license metadata and integration policy; it is not legal advice.",
        "",
        "Commercial solver binaries, license files, and proprietary libraries must not be committed.",
        "GPL tools are kept in separate processes or environments with file-exchange adapters unless reviewed separately.",
        "",
    ]
    for tool in registry.tools:
        lines.extend(
            [
                f"## {tool['canonical_name']}",
                "",
                f"- Upstream: {tool['upstream_repository']}",
                f"- Pinned ref: `{tool['pinned_ref']}`",
                f"- Resolved commit: `{tool['pinned_commit']}`",
                f"- Source archive SHA-256: `{tool['source_archive_sha256']}`",
                f"- SPDX license identifier: `{tool['spdx_license']}`",
                f"- Copyright holder: {tool['copyright_holder']}",
                f"- Install mode: {tool['install_mode']}",
                f"- Integration mode: {tool['integration_mode']}",
                f"- Redistributes source: {str(tool['redistribute_source']).lower()}",
                f"- Redistributes binaries: {str(tool['redistribute_binaries']).lower()}",
                f"- Adapter module: `{tool['adapter_module']}`",
                f"- Dataset license: {tool.get('dataset_license', 'not_recorded')}",
                f"- Human review required: {str(tool.get('human_review_required', False)).lower()}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    NOTICES.write_text(render_notices(), encoding="utf-8")
    print(f"wrote {NOTICES.relative_to(NOTICES.parents[0]) if False else NOTICES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
