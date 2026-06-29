"""Prepare and optionally execute FastCap/FasterCap for the IDC benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from textlayout import build_default_workflow
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation import prepare_idc_fastercap, run_fastercap


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("layout", type=Path)
    parser.add_argument("--out", type=Path, default=Path("simulation/idc_fastercap/work"))
    parser.add_argument("--executable", help="FasterCap/FastCap executable name or path.")
    args = parser.parse_args()

    spec = LayoutSpec.model_validate_json(args.layout.read_text(encoding="utf-8"))
    workflow = build_default_workflow()
    generated = workflow.run(spec, formats=())
    if not generated.report.passed:
        print(json.dumps({"status": "failed", "reason": generated.report.errors}))
        return 1
    prepared = prepare_idc_fastercap(
        spec,
        generated.geometry,
        workflow.technology(spec.technology),
        args.out,
    )
    result = run_fastercap(prepared, executable=args.executable)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.status == "executed" else 2 if result.status == "skipped" else 1


if __name__ == "__main__":
    raise SystemExit(main())
