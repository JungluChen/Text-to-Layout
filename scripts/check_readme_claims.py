"""Fail when advertised textlayout capabilities lack code, tests, or artifacts."""

from __future__ import annotations

import json
from pathlib import Path


COMPONENTS = {
    "IDC": ("idc.py", "idc.py", "01_idc_0p6pf"),
    "CPW": ("cpw.py", "cpw.py", "02_cpw_50ohm"),
    "SpiralInductor": ("spiral.py", "spiral.py", "03_spiral_inductor"),
    "QuarterWaveResonator": ("resonator.py", "resonator.py", "04_quarter_wave_resonator"),
    "SQUID": ("squid.py", "squid.py", "05_squid_loop"),
}


def validate_claims(root: Path) -> list[str]:
    errors: list[str] = []
    readme = (root / "README.md").read_text(encoding="utf-8")
    tests_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / "tests" / "textlayout_suite").glob("test_*.py")
    )
    for component, (schema, generator, benchmark) in COMPONENTS.items():
        if component not in readme:
            errors.append(f"README has no status claim for {component}")
        if not (root / "src" / "textlayout" / "schemas" / "dsl" / schema).is_file():
            errors.append(f"{component}: schema missing")
        if not (root / "src" / "textlayout" / "generators" / generator).is_file():
            errors.append(f"{component}: generator missing")
        folder = root / "examples" / "benchmarks" / benchmark
        if not (folder / "layout.json").is_file():
            errors.append(f"{component}: example DSL missing")
        if not (folder / "verification.json").is_file():
            errors.append(f"{component}: verifier artifact missing")
        if component not in tests_text and benchmark not in tests_text:
            errors.append(f"{component}: no verifier/generator test coverage found")

    for folder in (root / "examples" / "benchmarks").glob("*"):
        if not folder.is_dir() or not (folder / "layout.json").is_file():
            continue
        layout = json.loads((folder / "layout.json").read_text(encoding="utf-8"))
        if layout.get("metadata", {}).get("solver_executed"):
            verification = json.loads(
                (folder / "verification.json").read_text(encoding="utf-8")
            )
            outputs = verification.get("simulation_evidence", {}).get(
                "solver_output_files", []
            )
            if not outputs or not all((folder / path).is_file() for path in outputs):
                errors.append(f"{folder.name}: solver execution claimed without output artifact")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = validate_claims(root)
    for error in errors:
        print(f"FAIL  {error}")
    if errors:
        return 1
    print("README claim audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
