"""Minimal end-to-end demo of the textlayout deterministic core.

Run:  uv run --no-sync python examples/textlayout_cpw_demo.py [out_dir]

Shows the full slice: build a Layout DSL spec -> GeometryEngine -> validators ->
JSON + SVG exporters. No AI, no network, fully deterministic.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from textlayout import build_default_workflow
from textlayout.schemas.dsl import LayoutSpec


def main(out_dir: str = ".") -> int:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    spec = LayoutSpec(
        component="CPW",
        technology="generic_2metal",
        parameters={
            "center_width_um": 10,
            "gap_um": 6,
            "length_um": 1000,
            "ground_width_um": 50,
            "metal": "M1",
        },
        metadata={"intent": "50-ohm CPW feedline, demo"},
    )

    workflow = build_default_workflow()
    result = workflow.run(spec, formats=("json", "svg"))

    (out / "cpw.json").write_text(result.artifacts["json"], encoding="utf-8")
    (out / "cpw.svg").write_text(result.artifacts["svg"], encoding="utf-8")

    print(json.dumps(result.summary, indent=2))
    print(f"\nValidation passed: {result.report.passed}")
    print(f"Artifacts written to: {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
