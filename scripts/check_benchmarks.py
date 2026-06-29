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
        status = spec.get("metadata", {}).get("benchmark_status", "todo")
        names = {path.name for path in folder.iterdir()}
        relative = folder.relative_to(repo_root).as_posix()
        row = next((line for line in readme_text.splitlines() if relative in line), "")

        if status == "ready":
            missing = sorted(READY_REQUIRED - names)
            if missing:
                errors.append(f"{folder.name}: READY benchmark missing {missing}")
            verification_path = folder / "verification.json"
            if verification_path.is_file():
                verification = json.loads(verification_path.read_text(encoding="utf-8"))
                if verification.get("status") != "pass":
                    errors.append(f"{folder.name}: READY benchmark verification is not pass")
            if "PASS:" not in row:
                errors.append(f"{folder.name}: README row lacks explicit PASS checks")
            plan = folder / "simulation_plan.md"
            if plan.is_file() and "Level 2" not in plan.read_text(encoding="utf-8"):
                errors.append(f"{folder.name}: expected simulation readiness Level 2")
            simulation_dir = folder / "simulation"
            if not simulation_dir.is_dir() or not any(simulation_dir.iterdir()):
                errors.append(f"{folder.name}: Level 2 benchmark lacks prepared simulation inputs")
            elif not (simulation_dir / "simulation_manifest.json").is_file():
                errors.append(f"{folder.name}: simulation manifest is missing")
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
