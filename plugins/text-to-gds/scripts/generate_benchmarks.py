"""Regenerate evidence-backed Text-to-Layout benchmark artifacts.

Only benchmarks with ``metadata.benchmark_status == "ready"`` are generated.
Roadmap entries remain explicit TODOs and never receive fake geometry files.

Determinism (see ``docs/artifact_policy.md``)
---------------------------------------------
By default this script is *reproducible*:

* committed ``generated_at`` is normalized (the wall-clock time and tool
  versions are written to a git-ignored ``.generation_meta.json`` sidecar),
* the GDS top cell is renamed to a stable name (no random UUID suffix),
* a benchmark whose ``layout.json`` is unchanged is skipped rather than
  rewritten, so running the script twice in a row yields no git diff.

Pass ``--force`` to regenerate up-to-date benchmarks and ``--allow-timestamps``
to embed the wall-clock time (non-reproducible; debugging only).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import textlayout
from textlayout import build_default_workflow
from textlayout.exporters.gds_exporter import canonicalize_gds
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation import simulate_layout
from textlayout.verification import Check, CheckStatus, VerificationReport

REQUIRED_INPUTS = ("prompt.md", "layout.json")
FORMATS = ("gds", "svg", "json", "png")

# Committed artifacts that, together with a matching provenance hash, mean a
# benchmark is up to date and may be skipped (see ``_artifacts_current``).
READY_ARTIFACTS = (
    "output.gds",
    "output.svg",
    "output.json",
    "output.png",
    "verification.json",
    "evidence.md",
    "analytical_estimate.md",
    "simulation_plan.md",
    "report.md",
)

# Sentinel written instead of a wall-clock time so committed JSON is stable.
NORMALIZED_TIMESTAMP = "normalized"


def _layout_sha256(folder: Path) -> str:
    return hashlib.sha256((folder / "layout.json").read_bytes()).hexdigest()


def _provenance_block(folder: Path, *, deterministic: bool) -> dict[str, object]:
    """Reproducibility provenance; ``layout_json_sha256`` detects stale artifacts.

    In deterministic mode ``generated_at`` is normalized so committed bytes are
    stable; the real wall-clock time lands in a git-ignored sidecar instead.
    """
    layout_path = folder / "layout.json"
    generated_at: str = (
        NORMALIZED_TIMESTAMP if deterministic else datetime.now(timezone.utc).isoformat()
    )
    return {
        "layout_json_sha256": hashlib.sha256(layout_path.read_bytes()).hexdigest(),
        "generator_version": textlayout.__version__,
        "generated_at": generated_at,
        "timestamp_normalized": deterministic,
        "source_layout_path": layout_path.relative_to(folder.parents[1]).as_posix(),
    }


def _write_generation_meta(folder: Path) -> None:
    """Record the real (non-reproducible) generation metadata out of version control."""
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator_version": textlayout.__version__,
        "layout_json_sha256": _layout_sha256(folder),
    }
    (folder / ".generation_meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )


def _artifacts_current(folder: Path) -> bool:
    """True when committed artifacts already match the current ``layout.json``.

    Compares the recorded ``layout_json_sha256`` against the live hash so a
    benchmark is only regenerated when its source DSL actually changed. This is
    what makes a second run a no-op (no git diff)."""
    if any(not (folder / name).is_file() for name in READY_ARTIFACTS):
        return False
    sha = _layout_sha256(folder)
    for name in ("output.json", "verification.json"):
        try:
            data = json.loads((folder / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        provenance = data.get("provenance")
        if not isinstance(provenance, dict):
            return False
        if provenance.get("layout_json_sha256") != sha:
            return False
        if provenance.get("generator_version") != textlayout.__version__:
            return False
    return True


def _section_status(checks: list[Check]) -> str:
    return "fail" if any(c.status is CheckStatus.FAIL for c in checks) else "pass"


def _assemble_verification(spec, final_report, research, simulation, provenance):  # noqa: ANN001
    """Build the separated verification.json from research + simulation + checks.

    Separating geometry/artifact/analytical/simulation/physics/fabrication status
    is what keeps the report honest: a geometry pass never implies physics or
    fabrication readiness.
    """
    geom = [c for c in final_report.checks if not c.name.startswith("output_")]
    art = [c for c in final_report.checks if c.name.startswith("output_")]
    input_files = sorted(
        {
            Path(p).name
            for p in simulation.artifacts.values()
            if isinstance(p, str) and Path(p).suffix
        }
    )
    solver_executed = simulation.status == "executed"
    # Solver-OWNED output files only exist after a real execution; never before.
    solver_output_files = input_files if solver_executed else []
    estimates = dict(research.analytical_estimates)
    target_error_percent = next(
        (v for k, v in estimates.items() if "vs_target_pct" in k or "target_error" in k),
        None,
    )
    return {
        "status": final_report.status,
        "component": spec.component,
        "geometry_verification": {
            "status": _section_status(geom),
            "checks": [c.to_dict() for c in geom],
        },
        "artifact_verification": {
            "status": _section_status(art),
            "checks": [c.to_dict() for c in art],
        },
        "analytical_evidence": {
            "status": "analytical_only",
            "model": research.model_name,
            "target": dict(research.physical_target),
            "target_error_percent": target_error_percent,
            "estimates": estimates,
            "note": "Analytical estimate only; EM extraction required before any physics claim.",
        },
        "simulation_evidence": {
            "status": simulation.status,
            "solver_executed": solver_executed,
            "solver": simulation.solver,
            "readiness_level": simulation.readiness_level,
            "prepared_input_files": input_files,
            "solver_output_files": solver_output_files,
            "note": simulation.reason,
        },
        "physics_verification": {
            "status": "pending",
            "physics_verified": False,
            "note": "Requires solver execution and target comparison.",
        },
        "fabrication_readiness": {
            "status": "not_ready",
            "fabrication_ready": False,
            "note": "Requires process-specific DRC, EM simulation, and expert review.",
        },
        "warnings": final_report.warnings,
        "errors": final_report.errors,
        "provenance": provenance,
    }


def generate_benchmarks(
    root: Path,
    *,
    strict: bool = False,
    deterministic: bool = True,
    force: bool = False,
) -> int:
    workflow = build_default_workflow()
    failures: list[str] = []
    generated = 0
    skipped = 0

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

        if not force and _artifacts_current(folder):
            print(f"SKIP  {folder.name} (artifacts current)")
            skipped += 1
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
                if deterministic:
                    # Replace the random gdsfactory UUID top-cell suffix with a
                    # stable name so the committed GDS is byte-reproducible.
                    canonicalize_gds(folder / "output.gds", cell_name=spec.component)
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
                provenance = _provenance_block(folder, deterministic=deterministic)
                verification_doc = _assemble_verification(
                    spec, final_report, result.research, simulation, provenance
                )
                (folder / "verification.json").write_text(
                    json.dumps(verification_doc, indent=2) + "\n", encoding="utf-8"
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
                output_json = folder / "output.json"
                output_data = json.loads(output_json.read_text(encoding="utf-8"))
                output_data["provenance"] = provenance
                output_json.write_text(json.dumps(output_data, indent=2) + "\n", encoding="utf-8")
                _write_generation_meta(folder)
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
    print(f"Generated {generated} benchmark(s); skipped {skipped} up-to-date.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("examples/benchmarks"),
        help="Benchmark directory (default: examples/benchmarks).",
    )
    parser.add_argument("--strict", action="store_true", help="Treat TODO benchmarks as failures.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even when committed artifacts are already current.",
    )
    parser.add_argument(
        "--allow-timestamps",
        action="store_true",
        help="Embed wall-clock generated_at (non-reproducible; debugging only).",
    )
    args = parser.parse_args()
    if not args.root.is_dir():
        parser.error(f"benchmark root does not exist: {args.root}")
    return generate_benchmarks(
        args.root,
        strict=args.strict,
        deterministic=not args.allow_timestamps,
        force=args.force,
    )


if __name__ == "__main__":
    raise SystemExit(main())
