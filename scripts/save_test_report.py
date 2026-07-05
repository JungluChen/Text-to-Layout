"""Run pytest and save a machine-readable test report for the status manifest.

`scripts/generate_project_status.py` never runs pytest itself (a status
generator that silently re-runs the whole suite as a side effect is
surprising and slow); this script is the one place that does, and it writes
its result to `out/evidence/test_report.json` so the status manifest can
report a real, current count instead of a stale or guessed one.

Usage:
    python scripts/save_test_report.py [pytest args...]
    python scripts/save_test_report.py tests/textlayout_suite
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:]) or ["tests/textlayout_suite"]
    junit_path = ROOT / "out" / "evidence" / "pytest_junit.xml"
    junit_path.parent.mkdir(parents=True, exist_ok=True)

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", f"--junit-xml={junit_path}", *args],
        cwd=ROOT,
        check=False,
    )

    root = ElementTree.parse(junit_path).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        print("no <testsuite> element found in junit output", file=sys.stderr)
        return 1

    total = int(suite.attrib.get("tests", 0))
    failures = int(suite.attrib.get("failures", 0))
    errors = int(suite.attrib.get("errors", 0))
    skipped = int(suite.attrib.get("skipped", 0))
    passed = total - failures - errors - skipped

    report = {
        "source": f"pytest {' '.join(args)}",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "passed": passed,
        "failed": failures + errors,
        "skipped": skipped,
        "total": total,
    }
    report_path = ROOT / "out" / "evidence" / "test_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {report_path}: {report}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
