# Design, product surfaces and guidebook requirements — 2026-09-15

**Document class: MANUAL_DOCUMENTATION.** Documentation/automation update,
not an implemented UI or a new scientific certification. Timezone: Asia/Taipei.

## Changes

- A delegated design agent authored `Design.md` from the user-selected Apple
  Design Skill at `da2da6dd03aacf06da3fecf205347601d38bb141`, reading the skill,
  lookup, foundation and workbench references. The source is pinned and linked,
  not installed globally or copied into the product.
- Added `REQUIREMENTS.md` for CLI, Windows/macOS/Linux software, local/hosted
  browser, MCP, Codex and Claude Code plugins with shared scientific behavior.
- Added `docs/function-catalog.md`: 95 actual decorated legacy MCP functions
  and source signatures, with product capability mappings. Static inventory
  does not establish runtime availability, numerical correctness or host support.
- Added `docs/guidebook/README.md` with step-by-step CLI/API examples, AI prompts,
  an MCP call example, historical artifact illustration and the real screenshot /
  numbered-pointer capture requirements for each future interface.
- Linked existing UI/plugin documentation to the new authority and extended
  `to do list.md` with MCP/plugin and guidebook acceptance criteria.
- Updated the existing active automation to read and enforce these documents.
  Daily 01:00 Taipei timing, current task/model, direct-main verified publishing
  and normal notifications are preserved. Numerical correctness stays first.

## Validation and limitations

- The MCP inventory was extracted with Python AST from the remote baseline's
  `src/textlayout/_legacy/server.py`; names, signatures and descriptions were
  inspected without importing or executing solver tools.
- Existing Codex and Claude Code manifests were inspected. The Windows-specific
  root MCP launcher is documented as a portability gap, not silently advertised
  as a working Mac/Linux setup.
- Source baseline: `c0df0aaa99cb2de5c4baf6be181b4f313772979e`; local product
  changes/unpublished code remain untouched for their scheduled audit. The local
  uncommitted electrical-goal API is explicitly labeled pending publication.
- Product/solver tests, native installers, hosted service, actual plugin host
  calls and new GUI screenshots were not run/created in this documentation
  update. No feature or screenshot tutorial is marked implemented by a brief.
- Validation passed: all local Markdown targets in the eight changed documents,
  all 95 catalog/source tool names, sequential backlog headings 1–9 and six CLI
  help checks (`textlayout`, `prompt`, `generate`, `verify`, `doctor`, `serve`).
  Help checks used the remote-based source with the existing Python environment;
  they are not full tutorial execution. Full code gates remain required for
  product changes.

## Continuation

Publish only these documentation changes from the remote-based checkout and
record its commit/CI links in a follow-up report. Bring the documents into local
main without publishing the unaudited product commits. First scheduled work
still starts with numerical/reference auditing and Palace diagnosis. Implement
bounded UI/MCP/plugin slices using `Design.md`; capture and annotate the real
screens and verify matching commands/tool examples as each feature becomes
available. Do not substitute a wireframe or historical layout artifact for a
current application screenshot.
