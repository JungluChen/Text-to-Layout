"""Audit README benchmark links and READY/TODO artifact truthfulness."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

PROVENANCE_FIELDS = (
    "layout_json_sha256",
    "generator_version",
    "generated_at",
    "source_layout_path",
)


def _check_provenance(folder: Path, layout_sha: str) -> list[str]:
    """Validate reproducibility provenance and detect stale artifacts."""
    errors: list[str] = []
    for name in ("output.json", "verification.json"):
        path = folder / name
        if not path.is_file():
            errors.append(f"{folder.name}: missing {name} for provenance check")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        provenance = data.get("provenance")
        if not isinstance(provenance, dict):
            errors.append(f"{folder.name}: {name} missing provenance block")
            continue
        for field in PROVENANCE_FIELDS:
            if field not in provenance:
                errors.append(f"{folder.name}: {name} provenance missing {field}")
        recorded = provenance.get("layout_json_sha256")
        if recorded and recorded != layout_sha:
            errors.append(
                f"{folder.name}: {name} is STALE "
                f"(layout_json_sha256 {recorded[:12]} != current {layout_sha[:12]}); "
                "re-run scripts/generate_benchmarks.py"
            )
    return errors

READY_REQUIRED = {
    "prompt.md",
    "layout.json",
    "output.svg",
    "output.png",
    "output.gds",
    "output.json",
    "verification.json",
    "analytical_estimate.md",
    "simulation_plan.md",
    "evidence.md",
    "report.md",
}
TODO_REQUIRED = {"prompt.md", "layout.json", "TODO.md", "verification.json", "evidence.md"}
LINK_RE = re.compile(r"\]\(([^)]+)\)")

# Signatures of the OLD (1000x-too-small) 5 MHz LC table. These pair a
# capacitance with the wrong inductance unit; the corrected table never matches.
WRONG_5MHZ_PATTERNS = (
    re.compile(r"\|\s*1 pF\s*\|\s*1\.013\s*[μu]H"),  # 1 pF -> uH (should be mH)
    re.compile(r"\|\s*100 pF\s*\|\s*10\.13\s*nH"),  # 100 pF -> nH (should be uH)
    re.compile(r"borderline feasible"),
    re.compile(r"slightly above limit"),
)
# A benchmark-table "PASS" that is not qualified as "GEOMETRY PASS" is ambiguous.
AMBIGUOUS_PASS_RE = re.compile(r"(?<!GEOMETRY )PASS")


def check_benchmarks(root: Path, readme: Path, *, strict: bool = False) -> list[str]:
    errors: list[str] = []
    readme_text = readme.read_text(encoding="utf-8")
    repo_root = readme.parent

    for target in LINK_RE.findall(readme_text):
        clean = target.split("#", 1)[0]
        if clean.startswith("examples/benchmarks/") and not (repo_root / clean).exists():
            errors.append(f"README benchmark link does not exist: {clean}")

    # Benchmark-table rows must use qualified status labels (e.g. GEOMETRY PASS),
    # never a bare/ambiguous "PASS".
    for line in readme_text.splitlines():
        if "examples/benchmarks/" in line and AMBIGUOUS_PASS_RE.search(line):
            errors.append("README benchmark row uses an ambiguous 'PASS' without a qualifier")
            break

    for folder in sorted(path for path in root.iterdir() if path.is_dir()):
        layout_path = folder / "layout.json"
        if not layout_path.is_file():
            errors.append(f"{folder.name}: missing layout.json")
            continue
        spec = json.loads(layout_path.read_text(encoding="utf-8"))
        layout_sha = hashlib.sha256(layout_path.read_bytes()).hexdigest()
        metadata = spec.get("metadata", {})
        status = metadata.get("benchmark_status", "todo")
        names = {path.name for path in folder.iterdir()}
        relative = folder.relative_to(repo_root).as_posix()
        row = next((line for line in readme_text.splitlines() if relative in line), "")

        # Status-agnostic honesty checks on verification.json (apply to every
        # benchmark, not just ready ones).
        vpath = folder / "verification.json"
        if vpath.is_file():
            v = json.loads(vpath.read_text(encoding="utf-8"))
            phys = v.get("physics_verification", {})
            sim = v.get("simulation_evidence", {})
            if phys.get("physics_verified") and not sim.get("solver_executed"):
                errors.append(f"{folder.name}: physics_verified=true but solver_executed=false")
            if v.get("fabrication_readiness", {}).get("fabrication_ready"):
                errors.append(f"{folder.name}: fabrication_ready must not be true")

        # The 5 MHz LC benchmark must never regress to the old (wrong) table.
        if folder.name == "06_lc_5mhz_resonator":
            for md_name in ("feasibility.md", "evidence.md", "report.md", "TODO.md"):
                md_path = folder / md_name
                if md_path.is_file():
                    text = md_path.read_text(encoding="utf-8")
                    if any(p.search(text) for p in WRONG_5MHZ_PATTERNS):
                        errors.append(
                            f"{folder.name}/{md_name}: contains the old/incorrect 5 MHz LC table"
                        )

        if status == "ready":
            missing = sorted(READY_REQUIRED - names)
            if missing:
                errors.append(f"{folder.name}: READY benchmark missing {missing}")

            # Check metadata fields
            if "geometry_status" not in metadata:
                errors.append(f"{folder.name}: missing geometry_status in metadata")
            if "simulation_readiness_level" not in metadata:
                errors.append(f"{folder.name}: missing simulation_readiness_level in metadata")
            if "solver_executed" not in metadata:
                errors.append(f"{folder.name}: missing solver_executed in metadata")
            if "physics_verified" not in metadata:
                errors.append(f"{folder.name}: missing physics_verified in metadata")
            if "fabrication_ready" not in metadata:
                errors.append(f"{folder.name}: missing fabrication_ready in metadata")

            # Check verification.json structure
            verification_path = folder / "verification.json"
            if verification_path.is_file():
                verification = json.loads(verification_path.read_text(encoding="utf-8"))
                if verification.get("status") != "pass":
                    errors.append(f"{folder.name}: READY benchmark verification is not pass")

                # Check separated verification sections
                required_sections = [
                    "geometry_verification",
                    "artifact_verification",
                    "analytical_evidence",
                    "simulation_evidence",
                    "physics_verification",
                    "fabrication_readiness",
                ]
                for section in required_sections:
                    if section not in verification:
                        errors.append(f"{folder.name}: verification.json missing {section}")

                # Solver-owned output files must exist if execution is claimed.
                sim_evidence = verification.get("simulation_evidence", {})
                if sim_evidence.get("solver_executed") and not sim_evidence.get(
                    "solver_output_files"
                ):
                    errors.append(
                        f"{folder.name}: solver_executed=true but no solver_output_files listed"
                    )

            # Check for misleading claims in README row
            # Allow qualified PASS with colon or GEOMETRY PASS
            if "PASS:" not in row and "GEOMETRY PASS" not in row:
                errors.append(f"{folder.name}: README row lacks explicit PASS checks")

            # Check simulation plan
            plan = folder / "simulation_plan.md"
            level = 0
            if plan.is_file():
                match = re.search(r"Level (\d)", plan.read_text(encoding="utf-8"))
                level = int(match.group(1)) if match else 0
                if level < 1:
                    errors.append(f"{folder.name}: missing simulation readiness level")

            # Check simulation directory
            simulation_dir = folder / "simulation"
            if not simulation_dir.is_dir() or not any(simulation_dir.iterdir()):
                errors.append(f"{folder.name}: benchmark lacks a simulation plan manifest")
            elif not (simulation_dir / "simulation_manifest.json").is_file():
                errors.append(f"{folder.name}: simulation manifest is missing")
            elif level >= 2 and len(list(simulation_dir.iterdir())) < 2:
                errors.append(f"{folder.name}: Level 2 benchmark lacks prepared solver input")

            # Check for solver_executed claims without output files
            if metadata.get("solver_executed"):
                solver_outputs = list(simulation_dir.glob("*.csv")) + list(
                    simulation_dir.glob("*.s2p")
                )
                if not solver_outputs:
                    errors.append(
                        f"{folder.name}: solver_executed=true but no solver output files found"
                    )

            # Reproducibility provenance + stale-artifact detection.
            errors.extend(_check_provenance(folder, layout_sha))

            # An image must never exist without its source GDS.
            if (folder / "output.png").is_file() and not (folder / "output.gds").is_file():
                errors.append(f"{folder.name}: output.png exists but output.gds is missing")

        elif status == "geometry_candidate":
            # Special handling for SQUID-like benchmarks
            if "warning" not in metadata:
                errors.append(f"{folder.name}: geometry_candidate benchmark should have warning")

            missing = sorted(READY_REQUIRED - names)
            if missing:
                errors.append(f"{folder.name}: geometry_candidate benchmark missing {missing}")

        elif status == "infeasible":
            # Special handling for infeasible benchmarks
            if "infeasibility_reason" not in metadata:
                errors.append(f"{folder.name}: infeasible benchmark should have infeasibility_reason")
            if "feasible_alternative_frequency_hz" not in metadata:
                errors.append(f"{folder.name}: infeasible benchmark should have feasible_alternative_frequency_hz")
            # Check that no geometry was generated
            if list(folder.glob("output.*")):
                errors.append(f"{folder.name}: infeasible benchmark should not have output artifacts")
            if "INFEASIBLE" not in row and "infeasible" not in row.lower():
                errors.append(f"{folder.name}: README row should explain infeasibility")

        elif status == "todo":
            if strict:
                errors.append(f"{folder.name}: TODO benchmark is incomplete (strict mode)")
            missing = sorted(TODO_REQUIRED - names)
            if missing:
                errors.append(f"{folder.name}: TODO benchmark missing {missing}")
            if list(folder.glob("output.*")):
                errors.append(f"{folder.name}: TODO benchmark contains output artifacts")
            if "TODO" not in row:
                errors.append(f"{folder.name}: README row is not marked TODO")
            verification_path = folder / "verification.json"
            if verification_path.is_file():
                verification = json.loads(verification_path.read_text(encoding="utf-8"))
                if verification.get("status") != "todo":
                    errors.append(f"{folder.name}: TODO verification status is not todo")
            todo_path = folder / "TODO.md"
            if todo_path.is_file() and "PASS" in todo_path.read_text(encoding="utf-8"):
                errors.append(f"{folder.name}: TODO.md contains a PASS claim")
        else:
            errors.append(f"{folder.name}: unknown benchmark_status={status!r}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("examples/benchmarks"))
    parser.add_argument("--readme", type=Path, default=Path("README.md"))
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat incomplete (TODO) benchmarks as failures.",
    )
    args = parser.parse_args()
    errors = check_benchmarks(args.root, args.readme, strict=args.strict)
    for error in errors:
        print(f"FAIL  {error}")
    if errors:
        return 1
    print("Benchmark audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
