"""Audit cross-artifact evidence consistency for every showcase.

    uv run python scripts/audit_evidence_consistency.py            # human summary
    uv run python scripts/audit_evidence_consistency.py --json out.json

Exit 0 when every showcase's artifacts agree with its canonical evidence
record; exit 1 otherwise. Intended to gate CI.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from textlayout.evidence.consistency import audit, to_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", dest="json_out", help="Write the machine-readable report here.")
    args = parser.parse_args(argv)

    reports = audit(ROOT)
    payload = to_json(reports)

    if args.json_out:
        target = Path(args.json_out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {target}")

    for report in reports:
        mark = "OK  " if report.ok else "FAIL"
        print(f"[{mark}] {report.showcase_id}")
        for problem in report.problems:
            print(f"        - {problem}")

    bad = payload["showcases_with_problems"]
    total = payload["showcases_audited"]
    print(f"\n{total - bad}/{total} showcases consistent.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
