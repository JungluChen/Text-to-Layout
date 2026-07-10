"""Validate the external tool registry and write toolchain reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _common import (
    NOTICES,
    TOOLCHAIN_OUT,
    license_report,
    load_registry,
    sbom,
    tool_status,
    validate_registry,
    write_json,
)
from generate_notices import render_notices


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="run installed tool smoke tests")
    parser.add_argument("--benchmarks", action="store_true", help="run benchmark commands")
    parser.add_argument(
        "--check-notices",
        action="store_true",
        help="fail if THIRD_PARTY_NOTICES.md is missing or stale",
    )
    args = parser.parse_args()

    registry = load_registry()
    problems = validate_registry(registry)
    if args.check_notices:
        expected = render_notices()
        actual = NOTICES.read_text(encoding="utf-8") if NOTICES.is_file() else ""
        if actual != expected:
            problems.append("THIRD_PARTY_NOTICES.md is stale; run scripts/external/generate_notices.py")

    statuses = [
        tool_status(tool, smoke=args.smoke, benchmark=args.benchmarks)
        for tool in registry.tools
    ]
    payload = {
        "schema": "textlayout.external-tools.toolchain-report.v1",
        "registry_valid": not problems,
        "problems": problems,
        "tools": statuses,
    }
    write_json(TOOLCHAIN_OUT / "toolchain_report.json", payload)
    write_json(TOOLCHAIN_OUT / "license_report.json", license_report(registry))
    write_json(
        TOOLCHAIN_OUT / "benchmark_report.json",
        {
            "schema": "textlayout.external-tools.benchmark-report.v1",
            "benchmarks_requested": args.benchmarks,
            "tools": [
                {"id": item["id"], "benchmark": item["benchmark"]}
                for item in statuses
            ],
        },
    )
    write_json(TOOLCHAIN_OUT / "sbom.spdx.json", sbom(registry))

    print(json.dumps({"registry_valid": not problems, "problem_count": len(problems)}, indent=2))
    if problems:
        for problem in problems:
            print(f"ERROR: {problem}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
