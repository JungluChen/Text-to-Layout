"""Regenerate physics-fit acceptance packets under ``examples/acceptance/``.

An acceptance packet records the *verdict* (INFEASIBLE / GEOMETRY_PASS /
PHYSICS_VERIFIED) and the evidence ladder, not heavy binary artifacts. Geometry
for the feasible cases is built in a throwaway directory to confirm it verifies;
the reproducible GDS lives with the matching benchmark (see ``report.md``).

Deterministic: the written ``result.json`` and ``evidence.md`` contain only
analytical values and verdicts — no timestamps — so re-running yields no diff.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from textlayout.acceptance import (
    AcceptanceResult,
    evaluate_idc_autosize,
    evaluate_lc_resonator_feasibility,
    evaluate_quarter_wave_resonator,
)

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE = ROOT / "examples" / "acceptance"


def _build() -> list[AcceptanceResult]:
    with tempfile.TemporaryDirectory(prefix="textlayout-acceptance-") as tmp:
        work = Path(tmp)
        return [
            evaluate_lc_resonator_feasibility(5e6),
            evaluate_quarter_wave_resonator(6.0, work_dir=work / "b"),
            evaluate_idc_autosize(0.6, work_dir=work / "c"),
        ]


def generate(root: Path = ACCEPTANCE) -> int:
    root.mkdir(parents=True, exist_ok=True)
    for result in _build():
        folder = root / result.name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "prompt.md").write_text(
            f"# Prompt — {result.name}\n\n{result.prompt}\n", encoding="utf-8"
        )
        (folder / "result.json").write_text(
            json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8"
        )
        (folder / "evidence.md").write_text(result.to_markdown(), encoding="utf-8")
        print(f"{result.verdict:16s} {result.name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ACCEPTANCE)
    args = parser.parse_args()
    return generate(args.root)


if __name__ == "__main__":
    raise SystemExit(main())
