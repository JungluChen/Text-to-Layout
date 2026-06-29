"""Audit README benchmark links and READY/TODO artifact truthfulness."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

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


def check_benchmarks(root: Path, readme: Path) -> list[str]:
    errors: list[str] = []
    readme_text = readme.read_text(encoding="utf-8")
    repo_root = readme.parent

    for target in LINK_RE.findall(readme_text):
        clean = target.split("#", 1)[0]
        if clean.startswith("examples/benchmarks/") and not (repo_root / clean).exists():
            errors.append(f"README benchmark link does not exist: {clean}")

    for folder in sorted(path for path in root.iterdir() if path.is_dir()):
        layout_path = folder / "layout.json"
        if not layout_path.is_file():
            errors.append(f"{folder.name}: missing layout.json")
            continue
        spec = json.loads(layout_path.read_text(encoding="utf-8"))
        metadata = spec.get("metadata", {})
        status = metadata.get("benchmark_status", "todo")
        names = {path.name for path in folder.iterdir()}
        relative = folder.relative_to(repo_root).as_posix()
        row = next((line for line in readme_text.splitlines() if relative in line), "")

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

                # Check simulation evidence
                sim_evidence = verification.get("simulation_evidence", {})
                if sim_evidence.get("solver_executed") and not sim_evidence.get("input_files"):
                    errors.append(
                        f"{folder.name}: solver_executed=true but no input_files listed"
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
    args = parser.parse_args()
    errors = check_benchmarks(args.root, args.readme)
    for error in errors:
        print(f"FAIL  {error}")
    if errors:
        return 1
    print("Benchmark audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
