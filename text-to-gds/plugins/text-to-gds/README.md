# Text-to-GDS Plugin

This plugin bundles the Text-to-GDS MCP server and agent skill for local
Codex/Claude installs.

Codex consumes `.codex-plugin/plugin.json`. Claude Code consumes
`.claude-plugin/plugin.json`. The MCP server is configured through `.mcp.json`.

The bundled skill is copied from the root `skills/text-to-gds` directory. Keep
the root package and skill as source, then refresh this plugin copy before
publishing.

