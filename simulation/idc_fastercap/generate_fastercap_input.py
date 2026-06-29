"""Prepare FastCap/FasterCap IDC input from a verified Layout DSL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from textlayout import build_default_workflow
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation import prepare_idc_fastercap


def generate(layout_path: Path, output_dir: Path) -> dict[str, object]:
    spec = LayoutSpec.model_validate_json(layout_path.read_text(encoding="utf-8"))
    workflow = build_default_workflow()
    generated = workflow.run(spec, formats=())
    if not generated.report.passed:
        raise ValueError(f"Layout verification failed: {generated.report.errors}")
    result = prepare_idc_fastercap(
        spec,
        generated.geometry,
        workflow.technology(spec.technology),
        output_dir,
    )
    return result.to_dict()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("layout", type=Path)
    parser.add_argument("--out", type=Path, default=Path("simulation/idc_fastercap/work"))
    args = parser.parse_args()
    try:
        result = generate(args.layout, args.out)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
