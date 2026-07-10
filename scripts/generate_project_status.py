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
STATUS_SCHEMA = "textlayout.project-status.v2"

#: Statuses that count as real solver-backed evidence (mirrors the shared
#: evidence vocabulary in textlayout.evidence / textlayout.simulation.evidence).
_SOLVER_BACKED_STATUSES = frozenset({"PHYSICS_VERIFIED", "SIMULATION_EXECUTED"})
_SKIPPED_STATUSES = frozenset({"SKIPPED_SOLVER_ABSENT"})
_ANALYTICAL_STATUSES = frozenset({"ANALYTICAL_ONLY"})
_INVALID_STATUSES = frozenset({"SIMULATION_INVALID", "CONVERGENCE_FAILED", "FAILED"})


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
    invalid_or_failed: list[str] = []
    unclassified: list[str] = []
    by_status: dict[str, list[str]] = {}
    for example in examples:
        example_id = example.get("id", "unknown")
        status = example.get("evidence_status") or example.get("simulation_status")
        status_name = str(status or "UNCLASSIFIED")
        by_status.setdefault(status_name, []).append(example_id)
        if status in _SOLVER_BACKED_STATUSES:
            solver_backed.append(example_id)
        elif status in _SKIPPED_STATUSES:
            skipped.append(example_id)
        elif status in _ANALYTICAL_STATUSES:
            analytical_only.append(example_id)
        elif status in _INVALID_STATUSES:
            invalid_or_failed.append(example_id)
        else:
            unclassified.append(example_id)
    return {
        "solver_backed": solver_backed,
        "skipped_solver_absent": skipped,
        "analytical_only": analytical_only,
        "invalid_or_failed": invalid_or_failed,
        "unclassified": unclassified,
        "by_status": dict(sorted(by_status.items())),
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


def _read_junit_report() -> dict[str, Any] | None:
    """Parse the JUnit XML that pytest actually produces.

    Preferred over the hand-written JSON. The docstring below told contributors
    to create `test_report.xml`, while the reader only ever looked at
    `test_report.json` -- so the JSON sat untouched and PROJECT_STATUS reported
    `512 passed` long after the suite had grown past 600.
    """
    import xml.etree.ElementTree as ET

    xml_path = ROOT / "out" / "evidence" / "test_report.xml"
    if not xml_path.is_file():
        return None
    try:
        root = ET.parse(xml_path).getroot()
    except (ET.ParseError, OSError):
        return None
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        return None

    def count(name: str) -> int:
        return int(suite.get(name, 0) or 0)

    total, failed, skipped = count("tests"), count("failures") + count("errors"), count("skipped")
    raw_timestamp = suite.get("timestamp")
    if raw_timestamp:
        generated_at = datetime.fromisoformat(raw_timestamp).astimezone(timezone.utc).isoformat(
            timespec="seconds"
        )
    else:
        generated_at = datetime.fromtimestamp(
            xml_path.stat().st_mtime, tz=timezone.utc
        ).isoformat(timespec="seconds")
    return {
        "source": "pytest tests/textlayout_suite (out/evidence/test_report.xml)",
        "generated_at": generated_at,
        "passed": total - failed - skipped,
        "failed": failed,
        "skipped": skipped,
        "total": total,
    }


def _read_test_report() -> dict[str, Any] | None:
    """Read a saved test report, if one exists.

    This script never runs the test suite itself (a status generator that
    silently re-runs pytest as a side effect is surprising and slow). Produce
    the report first with:
        pytest -q tests/textlayout_suite --junit-xml=out/evidence/test_report.xml
    Absence is reported honestly, not filled with a stale or guessed number.
    """
    junit = _read_junit_report()
    if junit is not None:
        return junit
    report_path = ROOT / "out" / "evidence" / "test_report.json"
    if not report_path.is_file():
        return None
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _cli_commands() -> dict[str, list[str]]:
    """Introspect the real argparse tree — never a hand-maintained list.

    Returns {command: [subcommand, ...]} for every registered `textlayout`
    command, so the manifest reflects what `textlayout --help` actually
    exposes right now.
    """
    sys.path.insert(0, str(ROOT / "src"))
    from textlayout.cli import build_parser

    def _subchoices(parser: Any) -> dict[str, Any]:
        for action in parser._actions:  # noqa: SLF001 - argparse has no public API for this
            if getattr(action, "choices", None) and hasattr(action, "add_parser"):
                return dict(action.choices)
        return {}

    commands: dict[str, list[str]] = {}
    for name, sub in _subchoices(build_parser()).items():
        commands[name] = sorted(_subchoices(sub))
    return commands


def _epr_support(cli_commands: dict[str, list[str]]) -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "src"))
    from textlayout.epr import models as epr_models

    statuses = sorted(
        value
        for name, value in vars(epr_models).items()
        if name.startswith("EPR_STATUS") and isinstance(value, str)
    )
    return {
        "cli_command": "epr" in cli_commands,
        "prompt_verify_flag": "--include-epr",
        "statuses": statuses,
        "default_backend": (
            "analytical scaling model (EPR_ANALYTICAL_ONLY); a field-solver "
            "EPR (pyEPR/HFSS or Palace energies) is imported, never fabricated"
        ),
        "field_solver_verified_by_default": False,
    }


def _measurement_support(cli_commands: dict[str, list[str]]) -> dict[str, Any]:
    fixtures = ROOT / "examples" / "measurement_fixtures"
    return {
        "compare_command": "compare" in cli_commands.get("measurement", []),
        "calibrate_command": "calibrate" in cli_commands.get("measurement", []),
        "fixtures": sorted(p.name for p in fixtures.glob("*")) if fixtures.is_dir() else [],
        "fixtures_are_synthetic": True,
        "note": (
            "All committed measurement data is synthetic. Real fabrication "
            "confidence requires correlation against measured devices."
        ),
    }


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


def build_status(*, generated_at: str | None = None) -> dict[str, Any]:
    showcase_examples = _read_showcase_index()
    classification = _classify_showcase(showcase_examples)
    test_report = _read_test_report()
    cli_commands = _cli_commands()
    return {
        "schema": STATUS_SCHEMA,
        "generated_at": generated_at
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "package_version": _read_package_version(),
        "cli_commands": cli_commands,
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
        "epr_support": _epr_support(cli_commands),
        "measurement_support": _measurement_support(cli_commands),
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
        "## CLI commands (introspected from the real parser)",
        "",
        *(
            f"- `textlayout {name}`"
            + (f" — subcommands: {', '.join(f'`{s}`' for s in subs)}" if subs else "")
            for name, subs in sorted(status["cli_commands"].items())
        ),
        "",
        "## Showcase evidence",
        "",
        f"- Total examples: {status['showcase']['total_examples']}",
        f"- Solver-backed (`PHYSICS_VERIFIED`/`SIMULATION_EXECUTED`): "
        f"{', '.join(status['showcase']['solver_backed']) or '(none)'}",
        f"- Skipped (`SKIPPED_SOLVER_ABSENT`): "
        f"{', '.join(status['showcase']['skipped_solver_absent']) or '(none)'}",
        f"- Analytical only: {', '.join(status['showcase']['analytical_only']) or '(none)'}",
        f"- Invalid or failed: "
        f"{', '.join(status['showcase'].get('invalid_or_failed', [])) or '(none)'}",
        f"- Unclassified: "
        f"{', '.join(status['showcase'].get('unclassified', [])) or '(none)'}",
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
    epr = status["epr_support"]
    lines += [
        "",
        "## EPR / coherence support",
        "",
        f"- CLI command available: {epr['cli_command']} "
        f"(also `{epr['prompt_verify_flag']}` on `prompt`/`verify`)",
        f"- Statuses: {', '.join(f'`{s}`' for s in epr['statuses'])}",
        f"- Default backend: {epr['default_backend']}",
        f"- Field-solver verified by default: **{epr['field_solver_verified_by_default']}**",
    ]
    meas = status["measurement_support"]
    lines += [
        "",
        "## Measurement calibration support",
        "",
        f"- `measurement compare`: {meas['compare_command']} · "
        f"`measurement calibrate`: {meas['calibrate_command']}",
        f"- Committed fixtures are synthetic: **{meas['fixtures_are_synthetic']}** — "
        f"{meas['note']}",
    ]
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
    parser.add_argument(
        "--check", action="store_true", help="Fail instead of writing when generated output drifts."
    )
    args = parser.parse_args(argv)

    out_path = Path(args.out)
    md_path = Path(args.markdown_out)
    existing_timestamp: str | None = None
    if out_path.is_file():
        try:
            existing_timestamp = json.loads(out_path.read_text(encoding="utf-8")).get(
                "generated_at"
            )
        except (json.JSONDecodeError, OSError):
            pass
    if existing_timestamp is None and md_path.is_file():
        match = re.search(r"^Generated: ([^ ]+) ", md_path.read_text(encoding="utf-8"), re.M)
        if match:
            existing_timestamp = match.group(1)

    status = build_status(generated_at=existing_timestamp)
    expected_json = json.dumps(status, indent=2) + "\n"
    expected_markdown = render_markdown(status)

    if args.check:
        stale: list[str] = []
        if out_path.is_file() and out_path.read_text(encoding="utf-8") != expected_json:
            stale.append(str(out_path))
        if not md_path.is_file() or md_path.read_text(encoding="utf-8") != expected_markdown:
            stale.append(str(md_path))
        for path in stale:
            print(f"::error::stale generated project status: {path}")
        if stale:
            return 1
        print("project status artifacts are current.")
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(expected_json, encoding="utf-8")
    md_path.write_text(expected_markdown, encoding="utf-8")

    print(f"Wrote {out_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
