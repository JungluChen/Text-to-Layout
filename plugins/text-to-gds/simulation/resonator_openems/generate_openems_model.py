"""Prepare an openEMS manifest from verified quarter-wave resonator geometry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from textlayout import LayoutSpec, build_default_workflow
from textlayout.simulation import simulate_layout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("layout", type=Path)
    parser.add_argument("--out", type=Path, default=Path("simulation/resonator_openems/work"))
    args = parser.parse_args()
    spec = LayoutSpec.model_validate_json(args.layout.read_text(encoding="utf-8"))
    if spec.component != "QuarterWaveResonator":
        print(
            json.dumps(
                {"status": "failed", "reason": "Layout component must be QuarterWaveResonator."}
            )
        )
        return 1
    workflow = build_default_workflow()
    generated = workflow.run(spec, formats=())
    if not generated.report.passed:
        print(json.dumps({"status": "failed", "verification": generated.report.to_dict()}))
        return 1
    result = simulate_layout(
        spec, generated.geometry, workflow.technology(spec.technology), args.out, solver="openems"
    )
    print(json.dumps(result.to_dict()))
    return 0 if result.readiness_level >= 2 else 2


if __name__ == "__main__":
    raise SystemExit(main())
