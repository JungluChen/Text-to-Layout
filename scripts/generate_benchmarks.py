"""Regenerate evidence-backed Text-to-Layout benchmark artifacts.

Only benchmarks with ``metadata.benchmark_status == "ready"`` are generated.
Roadmap entries remain explicit TODOs and never receive fake geometry files.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from textlayout import build_default_workflow
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation import simulate_layout
from textlayout.verification import Check, CheckStatus, VerificationReport

REQUIRED_INPUTS = ("prompt.md", "layout.json")
FORMATS = ("gds", "svg", "json", "png")


def generate_benchmarks(root: Path, *, strict: bool = False) -> int:
    workflow = build_default_workflow()
    failures: list[str] = []
    generated = 0

    for folder in sorted(path for path in root.iterdir() if path.is_dir()):
        missing = [name for name in REQUIRED_INPUTS if not (folder / name).is_file()]
        if missing:
            failures.append(f"{folder.name}: missing {', '.join(missing)}")
            continue

        raw = json.loads((folder / "layout.json").read_text(encoding="utf-8"))
        status = raw.get("metadata", {}).get("benchmark_status", "todo")
        if status != "ready":
            print(f"TODO  {folder.name}")
            if strict:
                failures.append(f"{folder.name}: benchmark_status={status!r}")
            continue

        spec = LayoutSpec.model_validate(raw)
        with tempfile.TemporaryDirectory(prefix="textlayout-benchmark-") as tmp:
            result = workflow.run(spec, formats=FORMATS, output_dir=tmp, stem="output")
            (folder / "evidence.md").write_text(result.research.to_markdown(), encoding="utf-8")
            (folder / "analytical_estimate.md").write_text(
                result.research.analytical_estimate_markdown(), encoding="utf-8"
            )
            if not result.report.passed:
                (folder / "verification.json").write_text(
                    json.dumps(result.report.to_dict(), indent=2) + "\n", encoding="utf-8"
                )
                failures.append(f"{folder.name}: verification failed: {result.report.errors}")
                continue

            for fmt in FORMATS:
                source = Path(result.files[fmt])
                if not source.is_file() or source.stat().st_size == 0:
                    failures.append(f"{folder.name}: missing generated {fmt}")
                    break
                shutil.copyfile(source, folder / f"output.{fmt}")
            else:
                simulation = simulate_layout(
                    spec,
                    result.geometry,
                    workflow.technology(spec.technology),
                    folder / "simulation",
                )
                (folder / "simulation_plan.md").write_text(
                    simulation.to_markdown(), encoding="utf-8"
                )
                # Seed support files so the post-export existence audit can check
                # the complete final packet, including itself.
                (folder / "verification.json").write_text("{}\n", encoding="utf-8")
                (folder / "report.md").write_text("# Generating\n", encoding="utf-8")
                final_files = {
                    **{fmt: str(folder / f"output.{fmt}") for fmt in FORMATS},
                    "layout_dsl": str(folder / "layout.json"),
                    "verification": str(folder / "verification.json"),
                    "evidence": str(folder / "evidence.md"),
                    "analytical_estimate": str(folder / "analytical_estimate.md"),
                    "simulation_plan": str(folder / "simulation_plan.md"),
                    "report": str(folder / "report.md"),
                }
                base_checks = [
                    check for check in result.report.checks if not check.name.startswith("output_")
                ]
                for kind, filename in final_files.items():
                    path = Path(filename)
                    ok = path.is_file() and path.stat().st_size > 0
                    base_checks.append(
                        Check(
                            f"output_{kind}_exists",
                            CheckStatus.PASS if ok else CheckStatus.FAIL,
                            "" if ok else f"Expected output is missing or empty: {path}",
                        )
                    )
                final_report = VerificationReport.from_checks(spec.component, base_checks)
                (folder / "verification.json").write_text(
                    json.dumps(final_report.to_dict(), indent=2) + "\n", encoding="utf-8"
                )
                report_text = Path(result.files["report"]).read_text(encoding="utf-8")
                for kind, old_path in result.files.items():
                    if kind in final_files:
                        report_text = report_text.replace(old_path, final_files[kind])
                report_text = report_text.replace(
                    "No EM solver was executed by this workflow. The analytical estimate is a design starting point only.",
                    (
                        f"Simulation readiness is Level {simulation.readiness_level} "
                        f"({simulation.readiness_label}). No EM solver was executed; "
                        "the analytical estimate remains a design starting point only."
                    ),
                )
                (folder / "report.md").write_text(report_text, encoding="utf-8")
                generated += 1
                print(f"PASS  {folder.name}")

    readme = root.parents[1] / "README.md"
    for image in root.glob("*/output.png"):
        relative = image.relative_to(root.parents[1]).as_posix()
        if relative not in readme.read_text(encoding="utf-8"):
            failures.append(f"README does not reference {relative}")

    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        return 1
    print(f"Generated {generated} benchmark(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("examples/benchmarks"),
        help="Benchmark directory (default: examples/benchmarks).",
    )
    parser.add_argument("--strict", action="store_true", help="Treat TODO benchmarks as failures.")
    args = parser.parse_args()
    if not args.root.is_dir():
        parser.error(f"benchmark root does not exist: {args.root}")
    return generate_benchmarks(args.root, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
