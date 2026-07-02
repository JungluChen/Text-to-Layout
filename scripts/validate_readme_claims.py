"""Claim-validation gate: every README support claim must be backed by artifacts.

Run in CI *before* lint and tests:

    uv run python scripts/validate_readme_claims.py [--readme README.md]

Checks performed:

1. The ``## Component support matrix`` table exists and every row's claims map
   to real files: generator + schema ("Geometry"), research module
   ("Analytical estimate"), simulation plan artifact ("Solver input"), tests,
   and a benchmark folder.
2. Any "yes" in *Solver executed* requires a committed solver-owned output
   artifact (``solver.stdout.txt`` / ``simulation_result.json``) in the
   benchmark folder. Any "yes" in *Physics verified* additionally requires an
   evidence record whose status is ``PHYSICS_VERIFIED``.
3. The benchmark table must not contain **SIMULATION EXECUTED** or
   **PHYSICS VERIFIED** labels for a benchmark folder without those artifacts.
4. The ``## 30-second demo`` section and the honest limitation statement exist,
   and the demo command refers to a real CLI subcommand.

Exit code 0 = all claims verified; 1 = at least one unsupported claim.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LIMITATION_SENTENCE = "This project is not fabrication-ready by default."

#: Ground truth: what artifacts each supported component must have.
COMPONENTS: dict[str, dict[str, object]] = {
    "IDC": {
        "generator": "src/textlayout/generators/idc.py",
        "schema": "src/textlayout/schemas/dsl/idc.py",
        "research": "src/textlayout/research/idc_research.py",
        "tests": [
            "tests/textlayout_suite/test_idc_generator.py",
            "tests/textlayout_suite/test_from_text_workflow.py",
        ],
        "benchmark": "examples/benchmarks/01_idc_0p6pf",
    },
    "CPW": {
        "generator": "src/textlayout/generators/cpw.py",
        "schema": "src/textlayout/schemas/dsl/cpw.py",
        "research": "src/textlayout/research/cpw_research.py",
        "tests": ["tests/textlayout_suite/test_cpw_generator.py"],
        "benchmark": "examples/benchmarks/02_cpw_50ohm",
    },
    "SpiralInductor": {
        "generator": "src/textlayout/generators/spiral.py",
        "schema": "src/textlayout/schemas/dsl/spiral.py",
        "research": "src/textlayout/research/spiral_research.py",
        "tests": ["tests/textlayout_suite/test_extended_generators.py"],
        "benchmark": "examples/benchmarks/03_spiral_inductor",
    },
    "QuarterWaveResonator": {
        "generator": "src/textlayout/generators/resonator.py",
        "schema": "src/textlayout/schemas/dsl/resonator.py",
        "research": "src/textlayout/research/cpw_research.py",
        "tests": ["tests/textlayout_suite/test_extended_generators.py"],
        "benchmark": "examples/benchmarks/04_quarter_wave_resonator",
    },
    "SQUID": {
        "generator": "src/textlayout/generators/squid.py",
        "schema": "src/textlayout/schemas/dsl/squid.py",
        "research": "src/textlayout/research/squid_research.py",
        "tests": ["tests/textlayout_suite/test_extended_generators.py"],
        "benchmark": "examples/benchmarks/05_squid_loop",
    },
}

SOLVER_OUTPUT_NAMES = ("solver.stdout.txt", "simulation_result.json")

_ROW_RE = re.compile(r"^\|\s*(?P<cells>.+)\|\s*$")


def _fail(errors: list[str], message: str) -> None:
    errors.append(message)


def _existing_nonempty(root: Path, relative: str) -> bool:
    path = root / relative
    return path.is_file() and path.stat().st_size > 0


def _matrix_rows(readme_text: str) -> list[list[str]]:
    section = re.search(
        r"## Component support matrix\s*\n(.*?)(?:\n## |\Z)", readme_text, re.DOTALL
    )
    if section is None:
        return []
    rows: list[list[str]] = []
    for line in section.group(1).splitlines():
        match = _ROW_RE.match(line.strip())
        if match is None:
            continue
        cells = [cell.strip() for cell in match.group("cells").split("|")]
        if not cells or set(cells[0]) <= {"-", " ", ":"}:
            continue  # separator row
        rows.append(cells)
    return rows[1:] if rows else []  # drop header row


def _is_yes(cell: str) -> bool:
    return cell.strip().lower().startswith("yes")


def _solver_artifacts(root: Path, benchmark: str) -> list[Path]:
    bench = root / benchmark
    found: list[Path] = []
    if not bench.is_dir():
        return found
    for name in SOLVER_OUTPUT_NAMES:
        found.extend(p for p in bench.rglob(name) if p.is_file() and p.stat().st_size > 0)
    return found


def _check_matrix(readme_text: str, root: Path, errors: list[str]) -> None:
    rows = _matrix_rows(readme_text)
    if not rows:
        _fail(errors, "README is missing the '## Component support matrix' table")
        return
    listed = set()
    for cells in rows:
        if len(cells) < 7:
            _fail(errors, f"support-matrix row has too few columns: {cells}")
            continue
        component, geometry, analytical, solver_input, executed, verified, status = cells[:7]
        listed.add(component)
        spec = COMPONENTS.get(component)
        if spec is None:
            _fail(errors, f"support matrix lists unknown component {component!r}")
            continue
        if _is_yes(geometry):
            for key in ("generator", "schema"):
                if not _existing_nonempty(root, str(spec[key])):
                    _fail(errors, f"{component}: Geometry=yes but {spec[key]} is missing")
        if _is_yes(analytical) and not _existing_nonempty(root, str(spec["research"])):
            _fail(errors, f"{component}: Analytical=yes but {spec['research']} is missing")
        if _is_yes(solver_input) and not _existing_nonempty(
            root, f"{spec['benchmark']}/simulation_plan.md"
        ):
            _fail(
                errors,
                f"{component}: Solver input=yes but {spec['benchmark']}/simulation_plan.md "
                "is missing",
            )
        for test in spec["tests"]:  # type: ignore[union-attr]
            if not _existing_nonempty(root, str(test)):
                _fail(errors, f"{component}: advertised test {test} is missing")
        if not (root / str(spec["benchmark"])).is_dir():
            _fail(errors, f"{component}: benchmark folder {spec['benchmark']} is missing")
        if _is_yes(executed):
            artifacts = _solver_artifacts(root, str(spec["benchmark"]))
            if not artifacts:
                _fail(
                    errors,
                    f"{component}: 'Solver executed=yes' but no committed solver output "
                    f"({' or '.join(SOLVER_OUTPUT_NAMES)}) exists under {spec['benchmark']}",
                )
        if _is_yes(verified):
            if not _has_physics_verified_evidence(root, str(spec["benchmark"])):
                _fail(
                    errors,
                    f"{component}: 'Physics verified=yes' but no evidence record with "
                    f"status PHYSICS_VERIFIED exists under {spec['benchmark']}",
                )
    for known in COMPONENTS:
        if known not in listed:
            _fail(errors, f"component {known!r} exists in code but has no support-matrix row")


def _has_physics_verified_evidence(root: Path, benchmark: str) -> bool:
    bench = root / benchmark
    if not bench.is_dir():
        return False
    for candidate in bench.rglob("simulation.json"):
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for record in payload.get("evidence", []):
            if record.get("status") == "PHYSICS_VERIFIED" and all(
                (root / f).is_file() or Path(f).is_file() for f in record.get("output_files", [])
            ):
                return True
    return False


def _check_benchmark_table(readme_text: str, root: Path, errors: list[str]) -> None:
    # Only the benchmark table makes per-artifact claims; the status-vocabulary
    # table merely *defines* the labels and must not trip the check.
    section = re.search(r"## Layout Benchmarks\s*\n(.*?)(?:\n## |\Z)", readme_text, re.DOTALL)
    if section is None:
        return
    for line in section.group(1).splitlines():
        if not line.strip().startswith("|"):
            continue
        upper = line.upper()
        if "**SIMULATION EXECUTED**" not in upper and "**PHYSICS VERIFIED**" not in upper:
            continue
        folders = re.findall(r"\]\((examples/benchmarks/[^)\s]+)/?\)", line)
        if not folders:
            _fail(
                errors,
                "benchmark row claims solver execution but links no benchmark folder: "
                + line.strip()[:120],
            )
            continue
        for folder in folders:
            if not _solver_artifacts(root, folder):
                _fail(
                    errors,
                    f"benchmark row claims solver execution but {folder} has no solver "
                    "output artifact",
                )


def _check_demo_section(readme_text: str, errors: list[str]) -> None:
    if "## 30-second demo" not in readme_text:
        _fail(errors, "README is missing the '## 30-second demo' section")
        return
    demo_cmd = re.search(r"textlayout\s+(\w+)\s+\"", readme_text)
    if demo_cmd is None:
        _fail(errors, "30-second demo does not show a textlayout command")
    else:
        cli = (ROOT / "src/textlayout/cli.py").read_text(encoding="utf-8")
        subcommand = demo_cmd.group(1)
        if f'add_parser(\n        "{subcommand}"' not in cli and f'add_parser("{subcommand}"' not in cli:
            _fail(errors, f"demo uses 'textlayout {subcommand}' but the CLI has no such subcommand")
    if LIMITATION_SENTENCE not in readme_text:
        _fail(errors, f"README is missing the limitation statement: {LIMITATION_SENTENCE!r}")


def validate(readme: Path, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if not readme.is_file():
        return [f"README not found: {readme}"]
    text = readme.read_text(encoding="utf-8")
    _check_matrix(text, root, errors)
    _check_benchmark_table(text, root, errors)
    _check_demo_section(text, errors)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readme", default=str(ROOT / "README.md"))
    args = parser.parse_args(argv)
    errors = validate(Path(args.readme))
    if errors:
        print(f"README claim validation FAILED ({len(errors)} problem(s)):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print("README claim validation passed: every support claim is backed by artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
