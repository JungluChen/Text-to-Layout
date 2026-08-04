# Status-document authority

**Document class: MANUAL_DOCUMENTATION.** This file defines where current
claims live; it does not itself certify a platform or solver.

Current claims have one evidence path:

```text
out/evidence/*.json and out/platform/*.json
                    -> deterministic renderers
                    -> PROJECT_STATUS.md and docs/platforms/*.md
```

## Classification

| Document | Class | Authority boundary |
| --- | --- | --- |
| `PROJECT_STATUS.md` | `GENERATED_CURRENT_STATUS` | Package, CLI, test, showcase, PDK, measurement, and platform summary. |
| `docs/platforms/macos_arm64.md` | `GENERATED_CURRENT_STATUS` | macOS execution only; rendered from `out/platform/macos_arm64.json`. |
| `docs/platforms/wsl2_ubuntu.md` | `GENERATED_CURRENT_STATUS` | WSL2 execution or explicit blocker only; rendered from `out/platform/wsl2_ubuntu.json`. |
| `README.md` | `MANUAL_DOCUMENTATION` | Product overview and generated showcase blocks; links to current status instead of copying platform/test counts. |
| `AGENTS.md`, `CLAUDE.md` | `MANUAL_DOCUMENTATION` | Agent and development rules. Historical local tool snapshots are not current evidence. |
| `SIGNOFF_CRITERIA.md`, `SOLVER_EVIDENCE_CONTRACT.md` | `MANUAL_DOCUMENTATION` | Normative evidence requirements, not execution records. |
| `CURRENT_STATUS.md` | `LEGACY_SCOPE` | Legacy `examples/benchmarks/` status only. |
| `CLEAN_ROOM_VERIFICATION.md` | `HISTORICAL_RECORD` | An earlier clean-room run retained for provenance. |
| `PHYSICS_VALIDATION_REPORT.md` | `HISTORICAL_RECORD` | A June 2026 machine/tool snapshot, not current availability. |

Do not infer current support from a historical record or installation guide.
`FOUND` and `PROBE_PASS` are not solver execution. Platform certification must
come from the generated platform JSON and its matching Markdown rendering.

