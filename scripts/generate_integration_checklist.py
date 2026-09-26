"""Render the 100-candidate integration checklist from authoritative inventory.

Completion is explicit and evidence-backed. Discovery, imports, prepared input,
or a passing process exit do not qualify a target as integrated.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "src/textlayout/integrations/targets.json"
COMPLETED = ROOT / "docs/integrations/completed.json"
OUTPUT = ROOT / "docs/integrations/checklist.md"
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}\Z")


def render() -> str:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    completed = json.loads(COMPLETED.read_text(encoding="utf-8"))
    targets = catalog["targets"]
    if [target["id"] for target in targets] != list(range(1, 101)):
        raise ValueError("integration catalog must contain ordered IDs 1..100")
    records = completed["completed"]
    if not isinstance(records, dict):
        raise ValueError("completed must be a mapping keyed by candidate ID")
    known = {str(target["id"]) for target in targets}
    if set(records) - known:
        raise ValueError("completion record references an unknown candidate")
    for key, record in records.items():
        if not COMMIT_PATTERN.fullmatch(record.get("implementation_commit", "")):
            raise ValueError(f"candidate {key}: implementation_commit must be a full Git SHA")
        for field in ("source_license_evidence", "solver_evidence", "reference_evidence", "platform_evidence"):
            path = record.get(field)
            if not isinstance(path, str) or not path or not (ROOT / path).is_file():
                raise ValueError(f"candidate {key}: {field} must name an existing file")

    lines = [
        "# Integration completion checklist",
        "",
        "**Document class: GENERATED_DOCUMENTATION.** Generate with",
        "`python scripts/generate_integration_checklist.py`; verify with `--check`.",
        "This is the 100-slot user-requested candidate inventory, not a claim",
        "that 100 distinct open-source projects exist or are installable.",
        "Source hints in `targets.json` remain unverified until audited.",
        "",
        f"**Completed with full evidence: {len(records)}/100.**",
        "",
        "Check a target only after source/license/version review, a typed adapter",
        "using the shared evidence contract, an actual solver or tool execution,",
        "a source-backed numerical comparison when applicable, and verified",
        "platform operation. Record the implementation commit and evidence files",
        "in `docs/integrations/completed.json`; a later documentation commit",
        "records the implementation hash. Existing code or a doctor `FOUND`",
        "probe alone does not satisfy this checklist.",
        "",
    ]
    pillars = {pillar["id"]: pillar["name"] for pillar in catalog["pillars"]}
    for pillar_id in range(1, 11):
        lines.extend((f"## {pillar_id}. {pillars[pillar_id]}", ""))
        for target in targets:
            if target["pillar"] != pillar_id:
                continue
            key = str(target["id"])
            if key in records:
                commit = records[key]["implementation_commit"]
                lines.append(f"- [x] {target['id']:03d} {target['name']} — implementation `{commit}`; evidence in `completed.json`.")
            else:
                lines.append(f"- [ ] {target['id']:03d} {target['name']} — source/license, adapter, execution, comparison and platform acceptance pending.")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    generated = render()
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != generated:
            print(f"stale integration checklist: {OUTPUT}")
            return 1
        print("integration checklist is current")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(generated, encoding="utf-8")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
