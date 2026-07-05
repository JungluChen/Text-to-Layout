"""Generate the machine-readable project status manifest and its Markdown view.

Single source of truth for "what does this repo actually claim right now":
package version, showcase solver evidence, known limitations, and PDK
fabrication-readiness — collected by inspecting real committed artifacts, not
by re-stating prose from other docs. `scripts/check_project_claims.py`
consumes this manifest (plus the raw docs) to catch drift between them.

Usage:
    python scripts/generate_project_status.py [--out out/evidence/project_status.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STATUS_SCHEMA = "textlayout.project-status.v1"

#: Statuses that count as real solver-backed evidence (mirrors the shared
#: evidence vocabulary in textlayout.evidence / textlayout.simulation.evidence).
_SOLVER_BACKED_STATUSES = frozenset({"PHYSICS_VERIFIED", "SIMULATION_EXECUTED"})
_SKIPPED_STATUSES = frozenset({"SKIPPED_SOLVER_ABSENT"})


def _read_package_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _read_showcase_index() -> list[dict[str, Any]]:
    index_path = ROOT / "examples" / "showcase" / "index.json"
    if not index_path.is_file():
        return []
    data = json.loads(index_path.read_text(encoding="utf-8"))
    examples = data.get("examples", [])
    return examples if isinstance(examples, list) else []


def _classify_showcase(examples: list[dict[str, Any]]) -> dict[str, list[str]]:
    solver_backed: list[str] = []
    skipped: list[str] = []
    analytical_only: list[str] = []
    for example in examples:
        example_id = example.get("id", "unknown")
        status = example.get("evidence_status") or example.get("simulation_status")
        if status in _SOLVER_BACKED_STATUSES:
            solver_backed.append(example_id)
        elif status in _SKIPPED_STATUSES:
            skipped.append(example_id)
        else:
            analytical_only.append(example_id)
    return {
        "solver_backed": solver_backed,
        "skipped_solver_absent": skipped,
        "analytical_only": analytical_only,
    }


def _read_readme_limitations() -> list[str]:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(
        r"^## Limitations and next work\n(.*?)(?=\n## |\Z)", readme, re.S | re.M
    )
    if not match:
        return []
    return [
        line.lstrip("- ").strip()
        for line in match.group(1).splitlines()
        if line.strip().startswith("-")
    ]


def _read_test_report() -> dict[str, Any] | None:
    """Read a previously saved test report, if one exists.

    This script never runs the test suite itself (a status generator that
    silently re-runs pytest as a side effect is surprising and slow). Produce
    the report first with:
        pytest -q tests/textlayout_suite --junit-xml=out/evidence/test_report.xml
    or hand-write out/evidence/test_report.json with
        {"passed": N, "failed": N, "skipped": N, "source": "..."}.
    Absence is reported honestly, not filled with a stale or guessed number.
    """
    report_path = ROOT / "out" / "evidence" / "test_report.json"
    if not report_path.is_file():
        return None
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _pdk_status() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "src"))
    from textlayout.knowledge.technology_library import PDKS_DIR
    from textlayout.pdk import load_pdk

    pdks: list[dict[str, Any]] = []
    for pdk_path in sorted(PDKS_DIR.glob("*.yaml")):
        try:
            pdk = load_pdk(pdk_path)
        except Exception:  # noqa: BLE001 - a malformed example must not break status generation
            continue
        pdks.append(
            {
                "name": pdk.name,
                "version": pdk.version,
                "foundry_validated": pdk.foundry_validated,
                "source": pdk.source,
            }
        )
    any_foundry_validated = any(p["foundry_validated"] for p in pdks)
    return {
        "pdks": pdks,
        "any_foundry_validated": any_foundry_validated,
        "fabrication_readiness": (
            "NOT_FABRICATION_READY: no foundry-validated PDK is present"
            if not any_foundry_validated
            else "at least one foundry-validated PDK is present"
        ),
    }


def build_status() -> dict[str, Any]:
    showcase_examples = _read_showcase_index()
    classification = _classify_showcase(showcase_examples)
    test_report = _read_test_report()
    return {
        "schema": STATUS_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "package_version": _read_package_version(),
        "showcase": {
            "total_examples": len(showcase_examples),
            **classification,
        },
        "test_report": test_report
        or {
            "available": False,
            "note": "No saved test report at out/evidence/test_report.json; "
            "run pytest and save a report before trusting a test count here.",
        },
        "known_limitations": _read_readme_limitations(),
        "pdk_status": _pdk_status(),
    }


def render_markdown(status: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Project Status",
        "",
        f"Generated: {status['generated_at']} — by `scripts/generate_project_status.py`. "
        "Do not hand-edit; this file is a rendering of "
        "`out/evidence/project_status.json`.",
        "",
        f"- **Package version:** `{status['package_version']}`",
        "",
        "## Showcase evidence",
        "",
        f"- Total examples: {status['showcase']['total_examples']}",
        f"- Solver-backed (`PHYSICS_VERIFIED`/`SIMULATION_EXECUTED`): "
        f"{', '.join(status['showcase']['solver_backed']) or '(none)'}",
        f"- Skipped (`SKIPPED_SOLVER_ABSENT`): "
        f"{', '.join(status['showcase']['skipped_solver_absent']) or '(none)'}",
        f"- Analytical only: {', '.join(status['showcase']['analytical_only']) or '(none)'}",
        "",
        "## Tests",
        "",
    ]
    report = status["test_report"]
    if report.get("available", True) and "passed" in report:
        lines.append(
            f"- **{report['passed']} passed, {report.get('failed', 0)} failed, "
            f"{report.get('skipped', 0)} skipped** (source: {report.get('source', 'unknown')})"
        )
    else:
        lines.append(f"- No saved test report available. {report.get('note', '')}")
    lines += ["", "## PDK / fabrication readiness", ""]
    lines.append(f"- **{status['pdk_status']['fabrication_readiness']}**")
    lines.append("")
    lines.append("| PDK | Version | Foundry-validated | Source |")
    lines.append("| --- | --- | --- | --- |")
    for pdk in status["pdk_status"]["pdks"]:
        lines.append(
            f"| {pdk['name']} | {pdk['version']} | {pdk['foundry_validated']} | {pdk['source']} |"
        )
    lines += ["", "## Known limitations (from README)", ""]
    lines += [f"- {item}" for item in status["known_limitations"]]
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", default=str(ROOT / "out" / "evidence" / "project_status.json")
    )
    parser.add_argument(
        "--markdown-out", default=str(ROOT / "PROJECT_STATUS.md")
    )
    args = parser.parse_args(argv)

    status = build_status()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")

    md_path = Path(args.markdown_out)
    md_path.write_text(render_markdown(status), encoding="utf-8")

    print(f"Wrote {out_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
