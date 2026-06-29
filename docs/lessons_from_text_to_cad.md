# Lessons from Text-to-CAD

Study of [earthtojake/text-to-cad](https://github.com/earthtojake/text-to-cad)
(`marketplace.json` v0.3.7), performed by reading the live repository — tree,
`README.md`, `.claude-plugin/marketplace.json`, and `skills/cad/SKILL.md`.

## 1. What Text-to-CAD actually is

It is **a library of agent _Skills_** for CAD/robotics/fabrication, packaged as a
**Claude Code / Codex plugin** — *not* a hosted web API.

- **Distribution:** `npx skills install earthtojake/text-to-cad`, or
  `claude plugin marketplace add …` / `codex plugin marketplace add …`. A
  `.claude-plugin/marketplace.json` (and `.codex-plugin/marketplace.json`)
  declares one plugin (`cad`) pointing at `./plugins/cad`.
- **Runtime = the coding agent itself.** There is no server. A `SKILL.md` plus
  progressive `references/*.md` instruct the agent how to author **build123d**
  Python (`gen_step()`), then run CLI tools `scripts/step`, `scripts/inspect`,
  `scripts/snapshot`.
- **Packages:** `cadpy` (Python CAD on build123d) and `cadjs` (a Three.js/WebGL
  viewer); a `cad-viewer` skill launches a local browser preview.
- **Primary artifact = STEP.** STL/3MF/GLB are explicitly *secondary* exports
  branching from a STEP-first process.

## 2. How a prompt becomes a model (the part worth copying)

The `cad` skill enforces a **required workflow** — not free-form code generation:

1. Classify the task.
2. Load only the needed references.
3. Write a natural-language **CAD brief** (extract dims, units, intent, targets).
4. Plan parameters and expected bounding boxes **before** coding.
5. Edit *source*, not generated artifacts.
6. Generate explicit targets only.
7. **Validate geometrically** (`scripts/inspect refs … --facts --positioning`).
8. **Mandatory snapshot** of the primary STEP and review it.
9. **Repair-and-rerun** the smallest responsible source change on any failure.

Its non-negotiables include: *"Report only checks that actually ran"* and
*"keep STEP as the primary validated artifact."*

## 3. What to take into Text-to-Layout

| Lesson | How we apply it |
|---|---|
| **Validate before you trust the artifact** (inspect + mandatory snapshot loop) | Our `verification/` runs design-rule + geometry checks before export; `/layout/verify` is a first-class endpoint. |
| **Primary-artifact discipline** (STEP-first) | **GDS-first**: GDSII is the primary fabrication artifact; SVG/JSON are secondary previews. |
| **"Report only checks that actually ran"** | Each `Check` carries its measured value and the limit it was tested against; skipped checks are omitted, never faked. |
| **Structured, progressive instructions** (SKILL + references) | `docs/plugin_design.md`, `docs/tool_api.md`, and `simulation/*.md` document the workflow in layers. |
| **Plugin packaging via `marketplace.json`** | The repo already ships `.claude-plugin/` / `.codex-plugin/`; we add `docs/plugin_manifest.example.json` for the API-style tool. |
| **Great DX in the README** (one-line install, skills table, benchmark prompt→output table) | New README has architecture diagram, quick start, curl examples, DSL example, roadmap. |
| **Sensible defaults + minimal clarification** | DSL defaults (technology, outputs, rules fall back to the PDK); reject only what is physically impossible. |

## 4. What to deliberately NOT copy (IC layout ≠ mechanical CAD)

| Text-to-CAD | Why it does not transfer | Our divergence |
|---|---|---|
| **build123d / B-rep solids / STEP** | IC layout is 2.5-D planar polygons on process layers, not 3-D solids. | **gdsfactory + GDSII**, layer/datatype mapping. |
| **Three.js / WebGL mesh viewer (`cadjs`)** | No 3-D mesh to raymarch. | Lightweight **2-D SVG** preview (pure string, no GPU). |
| **Mechanical joints / mating / assembly datums** | Not the failure mode in IC layout. | **Design rules** (min width/gap/spacing, layer legality) — the *dangerous* part. |
| **Agent authors fairly free-form Python (build123d)** | Free-form geometry code is unsafe when geometry must satisfy DRC. | A constrained, typed **Layout DSL** — the AI never writes geometry code. |
| **Skill-only execution (no API)** | A ChatGPT custom GPT action needs callable HTTP endpoints. | We **add a FastAPI server** with clean JSON + OpenAPI, while keeping the MCP/skill path. |

## 5. One-line takeaway

Text-to-CAD's most valuable idea is *procedural distrust of generated geometry* —
a mandatory validate→snapshot→repair loop. We keep that idea and harden it for
IC layout (where a DRC violation is a scrapped wafer), but we replace its B-rep
runtime with a typed DSL + gdsfactory generator + a FastAPI tool surface.
