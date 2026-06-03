# Text-to-Layout

This repository collects local-first layout-generation tools for agentic EDA.

## Projects

- [text-to-gds](./text-to-gds/) - MCP tools, Codex/Claude plugin metadata, and
  gdsfactory PCells for superconducting GDSII layout generation.

Start with the Text-to-GDS guide:

```powershell
cd text-to-gds
py -3 -m uv sync
py -3 -m uv run pytest
```

