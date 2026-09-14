"""One-command local design: python demo.py --prompt 'Create a 50 ohm CPW'."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True, help="Device, target and fabrication constraints")
    parser.add_argument("--out", type=Path, default=ROOT / "out" / "demo")
    parser.add_argument("--tolerance", type=float, default=5.0, help="Target tolerance in percent")
    parser.add_argument("--no-solver", action="store_true", help="Generate and verify geometry only")
    parser.add_argument("--executable", help="Optional external physics solver path")
    parser.add_argument("--require-simulation", action="store_true",
                        help="Return a failure unless a solver result meets the target tolerance")
    args = parser.parse_args()
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".tools" / "matplotlib"))
    from textlayout import build_from_text_workflow
    from textlayout.evidence import EvidenceStatus
    from textlayout.research.design_rules import design_rules_for

    output = args.out.resolve()
    result = build_from_text_workflow().run(
        args.prompt, output, tolerance_percent=args.tolerance,
        execute_solver=not args.no_solver, solver_executable=args.executable)
    # A review bundle gives an AI caller the assumptions and evidence needed
    # to explain a design or request missing process information.
    review = dict(schema="textlayout.design-review.v1", request=args.prompt,
                  intent=result.intent.model_dump(mode="json"),
                  geometry_passed=result.ok, chosen_parameters=result.spec.parameters,
                  first_principles=result.generate.research.to_dict(),
                  engineering_rules=design_rules_for(result.intent.component),
                  simulation_status=result.evidence.status.value,
                  simulation_summary=result.evidence.summary_line(),
                  fabrication_ready=False,
                  learning_policy="Use measured calibration data with provenance; "
                                  "generated designs do not become measurement evidence.")
    (output / "design_review.json").write_text(json.dumps(review, indent=2) + "\n")
    print(json.dumps(result.to_dict(), indent=2))
    print(f"Design review: {output / 'design_review.json'}")
    print(f"Preview: {output / 'output.png'}")
    if not result.ok:
        return 1
    if args.require_simulation and result.evidence.status != EvidenceStatus.PHYSICS_VERIFIED:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
