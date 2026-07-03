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
import subprocess
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
    "TestStructure": {
        "generator": "src/textlayout/generators/test_structure.py",
        "schema": "src/textlayout/schemas/dsl/test_structure.py",
        "research": "src/textlayout/research/test_structure_research.py",
        "tests": ["tests/textlayout_suite/test_multi_device_generators.py"],
        "benchmark": "examples/showcase/03_idc_cpw_test_structure",
    },
    "TestChip": {
        "generator": "src/textlayout/generators/test_chip.py",
        "schema": "src/textlayout/schemas/dsl/test_chip.py",
        "research": "src/textlayout/research/test_chip_research.py",
        "tests": ["tests/textlayout_suite/test_multi_device_generators.py"],
        "benchmark": "examples/showcase/06_research_test_chip",
    },
}

#: Full artifact chain every showcased example must commit.
SHOWCASE_REQUIRED_FILES = (
    "prompt.txt",
    "intent.json",
    "layout.json",
    "output.gds",
    "output.svg",
    "output.png",
    "verification.json",
    "klayout_readback.json",
    "simulation.json",
    "optimization.json",
    "workflow_trace.json",
    "report.md",
    "README.md",
)

SOLVER_OUTPUT_NAMES = ("solver.stdout.txt", "solver.stderr.txt", "simulation_result.json")

STALE_README_CLAIMS = (
    "No benchmark in this repository is currently PHYSICS VERIFIED",
    "No benchmark is Level 3 or higher",
    "No benchmark achieves Level 3 or higher",
    "No benchmark achieves Level 4 or higher",
    "No benchmark achieves Level 5",
    "No benchmark achieves solver execution",
    "FasterCap/FastCap input is prepared, but not executed",
    "IDC capacitance is an analytical starting estimate, not solver or measurement evidence",
    "No benchmark is PHYSICS VERIFIED",
)

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


def _result_records(root: Path, benchmark: str) -> list[tuple[Path, dict[str, object]]]:
    bench = root / benchmark
    found: list[tuple[Path, dict[str, object]]] = []
    if not bench.is_dir():
        return found
    for path in bench.rglob("simulation_result.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            found.append((path, payload))
    return found


def _artifact_nonempty(result_path: Path, value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = Path(value)
    candidates = [path]
    if not path.is_absolute():
        candidates.extend((result_path.parent / path, result_path.parent / path.name))
    return any(candidate.is_file() and candidate.stat().st_size > 0 for candidate in candidates)


def _has_executed_evidence(root: Path, benchmark: str) -> bool:
    for result_path, payload in _result_records(root, benchmark):
        artifacts = payload.get("artifacts")
        if not isinstance(artifacts, dict):
            continue
        if payload.get("status") != "executed" or payload.get("solver_executed") is not True:
            continue
        if all(
            _artifact_nonempty(result_path, artifacts.get(key))
            for key in ("solver_stdout", "solver_stderr")
        ):
            return True
    return False


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
        if _is_yes(solver_input) and not (
            _existing_nonempty(root, f"{spec['benchmark']}/simulation_plan.md")
            or _existing_nonempty(root, f"{spec['benchmark']}/output.simulation_plan.md")
        ):
            _fail(
                errors,
                f"{component}: Solver input=yes but {spec['benchmark']} has no "
                "simulation_plan.md / output.simulation_plan.md",
            )
        for test in spec["tests"]:  # type: ignore[union-attr]
            if not _existing_nonempty(root, str(test)):
                _fail(errors, f"{component}: advertised test {test} is missing")
        if not (root / str(spec["benchmark"])).is_dir():
            _fail(errors, f"{component}: benchmark folder {spec['benchmark']} is missing")
        if _is_yes(executed):
            if not _has_executed_evidence(root, str(spec["benchmark"])):
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
    for result_path, payload in _result_records(root, benchmark):
        artifacts = payload.get("artifacts")
        comparison = payload.get("target_comparison")
        if not isinstance(artifacts, dict) or not isinstance(comparison, dict):
            continue
        if (
            payload.get("status") == "executed"
            and payload.get("solver_executed") is True
            and payload.get("capacitance_matrix_parsed") is True
            and comparison.get("within_tolerance") is True
            and all(
                _artifact_nonempty(result_path, artifacts.get(key))
                for key in ("solver_stdout", "solver_stderr")
            )
        ):
            return True
    return False


def _check_benchmark_table(readme_text: str, root: Path, errors: list[str]) -> None:
    # Only the benchmark table makes per-artifact claims; the status-vocabulary
    # table merely *defines* the labels and must not trip the check.
    section = re.search(
        r"## Legacy analytical benchmarks\s*\n(.*?)(?:\n## |\Z)",
        readme_text,
        re.DOTALL,
    )
    if section is None:
        return
    for line in section.group(1).splitlines():
        if not line.strip().startswith("|"):
            continue
        upper = line.upper()
        executed_claim = re.search(r"SIMULATION[_ ]EXECUTED", upper) is not None
        verified_claim = re.search(r"PHYSICS[_ ]VERIFIED", upper) is not None
        if not executed_claim and not verified_claim:
            continue
        folders = re.findall(r"\]\((examples/benchmarks/[^/)\s]+)(?:/[^)\s]*)?\)", line)
        if not folders:
            _fail(
                errors,
                "benchmark row claims solver execution but links no benchmark folder: "
                + line.strip()[:120],
            )
            continue
        for folder in folders:
            if executed_claim and not _has_executed_evidence(root, folder):
                _fail(
                    errors,
                    f"benchmark row claims solver execution but {folder} has no solver "
                    "execution result with non-empty stdout/stderr artifacts",
                )
            if verified_claim and not _has_physics_verified_evidence(root, folder):
                _fail(
                    errors,
                    f"benchmark row claims solver execution and PHYSICS_VERIFIED but {folder} "
                    "has no parsed "
                    "in-tolerance simulation result with non-empty stdout/stderr artifacts",
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


def _showcase_simulation(root: Path, folder: str) -> dict[str, object] | None:
    path = root / folder / "simulation.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _check_stale_claims(readme_text: str, errors: list[str]) -> None:
    for claim in STALE_README_CLAIMS:
        if claim.casefold() in readme_text.casefold():
            _fail(errors, f"README contains stale release claim: {claim!r}")


def _check_showcase_paths(root: Path, errors: list[str]) -> None:
    showcase = root / "examples" / "showcase"
    if not showcase.is_dir():
        _fail(errors, "examples/showcase is missing")
        return
    for path in showcase.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        normalized = text.replace("\\\\", "\\")
        if (
            re.search(r"[A-Za-z]:\\Users\\", normalized, re.IGNORECASE)
            or re.search(r"/mnt/[a-z]/Users/", text, re.IGNORECASE)
            or "/home/" + "lu/" in text
            or "/tmp/" + "fastercap_work" in text
        ):
            relative = path.relative_to(root)
            _fail(
                errors,
                f"committed showcase artifact contains an absolute user path: {relative}",
            )


#: File suffixes in scope for the repo-wide local-path leak gate. Covers the
#: JSON/Markdown/trace/report/manifest/README artifact families named in the
#: release-consistency contract.
_PATH_LEAK_SUFFIXES = frozenset({".json", ".md", ".markdown"})

#: A prefix immediately followed by one of these is a documentation
#: placeholder (e.g. ``/mnt/c/Users/<you>/...``), not a real leaked path.
_PLACEHOLDER_PREFIX = re.compile(r"^(<|\$\{?\w|%[A-Za-z_])")


#: Directories that are never part of the committed release surface — used
#: only as a fallback when ``git`` is unavailable (e.g. large gitignored
#: third-party clones such as ``external_repos/`` and ``quantum-eda-stack/``).
_PATH_LEAK_EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".venv",
        ".wsl-venv",
        ".tools",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "dist",
        "build",
        "external_repos",
        "quantum-eda-stack",
        "references",
        "external_references",
        "out",
    }
)


def _scannable_files(root: Path) -> list[Path]:
    """Files that are (or are about to be) part of the committed release
    surface: everything ``git`` already tracks, plus any new file that is not
    gitignored — so this gate catches a leak the instant it is written, not
    only after ``git add``.

    Falls back to a pruned filesystem walk when ``git`` is unavailable.
    """
    seen: set[Path] = set()
    ok = True
    for args in (["ls-files"], ["ls-files", "--others", "--exclude-standard"]):
        try:
            completed = subprocess.run(
                ["git", *args],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            ok = False
            break
        seen.update(root / line for line in completed.stdout.splitlines() if line.strip())
    if ok:
        return sorted(seen)

    found: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir():
                if entry.name in _PATH_LEAK_EXCLUDED_DIRS:
                    continue
                stack.append(entry)
            elif entry.is_file():
                found.append(entry)
    return found


def _find_local_path_leak(text: str) -> str | None:
    """Return a description of the first real (non-placeholder) path leak.

    Only the two username-revealing patterns are checked repo-wide: a bare
    ``/tmp/...`` or ``/home/...`` directory name is a portable Unix
    convention on its own and is legitimate in instructional documentation
    (e.g. AGENTS.md's WSL walkthrough); it is only a leak once it is paired
    with a real machine path, which the showcase-artifact scan
    (:func:`_check_showcase_paths`) already enforces for generated evidence.
    """
    normalized = text.replace("\\\\", "\\")
    for pattern, label in (
        (re.compile(r"[A-Za-z]:\\Users\\", re.IGNORECASE), "C:\\Users\\"),
        (re.compile(r"/mnt/[a-z]/Users/", re.IGNORECASE), "/mnt/c/Users/"),
    ):
        for match in pattern.finditer(normalized):
            tail = normalized[match.end() : match.end() + 24]
            if _PLACEHOLDER_PREFIX.match(tail):
                continue
            return label
    return None


def _check_no_committed_absolute_paths(root: Path, errors: list[str]) -> None:
    """Fail if any committed JSON/Markdown/trace/report/manifest/README file
    contains a real local absolute machine path (as opposed to a documented
    ``<placeholder>``/``$VAR``/``%VAR%`` template)."""
    for path in _scannable_files(root):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _PATH_LEAK_SUFFIXES and path.name.upper() != "README":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        leak = _find_local_path_leak(text)
        if leak is not None:
            relative = path.relative_to(root)
            _fail(
                errors,
                f"committed artifact contains a local absolute machine path "
                f"({leak}...): {relative}",
            )


#: Historical bug signatures: hardcoded quantity/unit phrasing that ignored
#: the evidence record's actual quantity (e.g. an inductance example report
#: claiming "capacitance"/"pF").
_CAPACITANCE_PHRASES = (
    "Analytical capacitance",
    "Solver-extracted capacitance",
    "Extracted mutual capacitance",
    "Target capacitance",
)
_INDUCTANCE_PHRASES = (
    "Analytical inductance",
    "Solver-extracted inductance",
    "Extracted inductance",
    "Target inductance",
)


def _evidence_quantity(root: Path, folder: str) -> str | None:
    simulation = _showcase_simulation(root, folder)
    if simulation is None:
        return None
    evidence_records = simulation.get("evidence")
    evidence = evidence_records[0] if isinstance(evidence_records, list) and evidence_records else {}
    if not isinstance(evidence, dict):
        return None
    quantity = evidence.get("quantity")
    return quantity if isinstance(quantity, str) else None


def _check_showcase_unit_language(root: Path, errors: list[str]) -> None:
    """Fail if a showcase example's report mixes up capacitance/inductance
    quantity language for its target/result values."""
    showcase = root / "examples" / "showcase"
    if not showcase.is_dir():
        return
    for folder_path in sorted(showcase.iterdir()):
        if not folder_path.is_dir():
            continue
        folder = f"examples/showcase/{folder_path.name}"
        quantity = _evidence_quantity(root, folder)
        if quantity is None:
            continue
        report_path = folder_path / "report.md"
        if not report_path.is_file():
            continue
        try:
            report_text = report_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if quantity == "inductance":
            for phrase in _CAPACITANCE_PHRASES:
                if phrase in report_text:
                    _fail(
                        errors,
                        f"{folder}: report.md is an inductance example but uses "
                        f"capacitance/pF language {phrase!r}",
                    )
        elif quantity == "capacitance":
            for phrase in _INDUCTANCE_PHRASES:
                if phrase in report_text:
                    _fail(
                        errors,
                        f"{folder}: report.md is a capacitance example but uses "
                        f"inductance/nH language {phrase!r}",
                    )


def _check_tile_simulation_map_summary(root: Path, errors: list[str]) -> None:
    """Fail if a tile_simulation_map.json exists but its example's committed
    report doesn't summarize full-tile status and every sub-block's evidence."""
    showcase = root / "examples" / "showcase"
    if not showcase.is_dir():
        return
    for folder_path in sorted(showcase.iterdir()):
        tile_map_path = folder_path / "tile_simulation_map.json"
        if not tile_map_path.is_file():
            continue
        folder = f"examples/showcase/{folder_path.name}"
        try:
            tile_map = json.loads(tile_map_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _fail(errors, f"{folder}: tile_simulation_map.json is unreadable")
            continue
        subblocks = tile_map.get("subblocks")
        expected_names = list(subblocks.keys()) if isinstance(subblocks, dict) else []
        for doc_name in ("report.md", "README.md"):
            doc_path = folder_path / doc_name
            if not doc_path.is_file():
                _fail(errors, f"{folder}: missing {doc_name} required by tile_simulation_map.json")
                continue
            text = doc_path.read_text(encoding="utf-8")
            upper = text.upper()
            if "FULL-TILE" not in upper and "FULL TILE" not in upper:
                _fail(
                    errors,
                    f"{folder}/{doc_name}: tile_simulation_map.json exists but the report "
                    "does not mention full-tile status",
                )
            missing_subblocks = [name for name in expected_names if name not in text]
            if missing_subblocks:
                _fail(
                    errors,
                    f"{folder}/{doc_name}: tile_simulation_map.json sub-blocks "
                    f"{missing_subblocks} are not summarized in the report",
                )
            if re.search(r"FULL[\s_-]TILE[^.\n]{0,40}(VERIFIED|EXECUTED)\b", upper) and (
                "NOT EXECUTED" not in upper and "NOT_MODELED" not in upper
            ):
                _fail(
                    errors,
                    f"{folder}/{doc_name}: report language suggests a full-tile solve "
                    "was verified/executed, which tile_simulation_map.json denies",
                )


_ROW_START_RE = re.compile(r"\|\s*[1-6]\s*\|")


def _check_showcase_table_formatting(readme_text: str, errors: list[str]) -> None:
    """Fail if the six-example table is collapsed into unreadable single lines."""
    section = re.search(
        r"## Six research-grade examples\s*\n(.*?)(?:\n## |\Z)", readme_text, re.DOTALL
    )
    if section is None:
        return
    for line in section.group(1).splitlines():
        if not line.strip().startswith("|"):
            continue
        if len(_ROW_START_RE.findall(line)) > 1:
            _fail(
                errors,
                "six-example table has more than one row collapsed onto a single "
                f"Markdown line: {line.strip()[:120]}...",
            )
        if len(line) > 4000:
            _fail(
                errors,
                "six-example table row exceeds a readable line length "
                f"({len(line)} chars); rows must not be collapsed",
            )


def _check_showcase(readme_text: str, root: Path, errors: list[str]) -> None:
    """Validate the six-example showcase table against committed artifacts."""
    section = re.search(
        r"## Six research-grade examples\s*\n(.*?)(?:\n## |\Z)", readme_text, re.DOTALL
    )
    if section is None:
        _fail(errors, "README is missing the '## Six research-grade examples' table")
        return
    expected_header = "| # | Target | Prompt | Output | Step Results | Evidence Status |"
    if expected_header not in section.group(1):
        _fail(errors, f"showcase table is missing required header: {expected_header}")
    rows = [
        line
        for line in section.group(1).splitlines()
        if line.strip().startswith("|") and "examples/showcase/" in line
    ]
    if len(rows) < 6:
        _fail(errors, f"showcase table lists {len(rows)} examples; six are required")
    for line in rows:
        folders = sorted(set(re.findall(r"examples/showcase/([\w-]+)", line)))
        if not folders:
            continue
        folder = f"examples/showcase/{folders[0]}"
        for name in SHOWCASE_REQUIRED_FILES:
            if not _existing_nonempty(root, f"{folder}/{name}"):
                _fail(errors, f"showcase row links {folder} but {name} is missing/empty")
        upper = line.upper()
        if "NOT_FABRICATION_READY" not in upper:
            _fail(errors, f"showcase row must state NOT_FABRICATION_READY: {folder}")
        simulation = _showcase_simulation(root, folder)
        if re.search(r"FABRICATION[_ ]READY", upper) and "NOT_FABRICATION_READY" not in upper:
            _fail(errors, f"showcase row claims FABRICATION_READY without signoff: {folder}")
        claims_verified = "PHYSICS_VERIFIED" in upper
        claims_executed = claims_verified or "SIMULATION_EXECUTED" in upper
        if claims_executed:
            if simulation is None:
                _fail(errors, f"{folder}: solver claim but simulation.json is unreadable")
                continue
            if simulation.get("solver_executed") is not True:
                _fail(errors, f"{folder}: README claims solver execution; artifacts say no")
            artifacts = simulation.get("artifacts")
            result_path = root / folder / "simulation.json"
            if not isinstance(artifacts, dict) or not all(
                _artifact_nonempty(result_path, artifacts.get(key))
                or _artifact_nonempty(
                    root / folder / "extraction" / "capacitance_input" / "x", artifacts.get(key)
                )
                for key in ("solver_stdout", "solver_stderr", "result")
            ):
                _fail(
                    errors,
                    f"{folder}: solver claim without committed stdout/stderr/result artifacts",
                )
            evidence_records = simulation.get("evidence")
            evidence = evidence_records[0] if isinstance(evidence_records, list) and evidence_records else {}
            if not isinstance(evidence, dict) or not isinstance(
                evidence.get("extracted_value"), (int, float)
            ):
                _fail(errors, f"{folder}: solver claim without a parsed extracted value")
            comparison = simulation.get("target_comparison")
            if not isinstance(comparison, dict):
                _fail(errors, f"{folder}: solver claim without target_comparison")
            elif isinstance(evidence, dict):
                target = evidence.get("target_value")
                extracted = evidence.get("extracted_value")
                error = comparison.get("error_pct")
                unit = evidence.get("target_unit") or evidence.get("extracted_unit") or ""
                if all(isinstance(value, (int, float)) for value in (target, extracted, error)):
                    expected_values = (
                        f"{float(target):.6f} {unit}".strip(),
                        f"{float(extracted):.6f} {unit}".strip(),
                        f"{abs(float(error)):.3f}%",
                    )
                    for value in expected_values:
                        if value not in line:
                            _fail(
                                errors,
                                f"{folder}: README row does not match simulation.json; "
                                f"missing {value!r}",
                            )
        if claims_verified:
            comparison = simulation.get("target_comparison") if simulation else None
            if not isinstance(comparison, dict) or comparison.get("within_tolerance") is not True:
                _fail(
                    errors,
                    f"{folder}: README claims PHYSICS_VERIFIED but the committed target "
                    "comparison is missing or out of tolerance",
                )
            artifacts = simulation.get("artifacts", {}) if simulation else {}
            evidence_records = simulation.get("evidence", []) if simulation else []
            evidence = evidence_records[0] if evidence_records else {}
            solver = str(simulation.get("solver", "")) if simulation else ""
            if folder.endswith("02_cpw_50ohm"):
                if "openems" not in solver.casefold() or not _artifact_nonempty(
                    root / folder / "simulation.json", artifacts.get("touchstone")
                ):
                    _fail(errors, f"{folder}: CPW verification requires openEMS Touchstone output")
                if evidence.get("quantity") != "characteristic_impedance":
                    _fail(errors, f"{folder}: CPW verification lacks parsed impedance evidence")
            if folder.endswith("04_spiral_inductor_3nh"):
                if "fasthenry" not in solver.casefold() or not _artifact_nonempty(
                    root / folder / "simulation.json", artifacts.get("zc_matrix")
                ):
                    _fail(errors, f"{folder}: spiral verification requires FastHenry Zc.mat output")
                if evidence.get("quantity") != "inductance":
                    _fail(errors, f"{folder}: spiral verification lacks extracted inductance")
            if folder.endswith("05_quarter_wave_resonator_6ghz"):
                if "openems" not in solver.casefold() or not _artifact_nonempty(
                    root / folder / "simulation.json", artifacts.get("touchstone")
                ):
                    _fail(errors, f"{folder}: resonator verification requires openEMS Touchstone output")
                if evidence.get("quantity") != "resonance_frequency":
                    _fail(errors, f"{folder}: resonator verification lacks parsed resonance frequency")
        if folder.endswith("06_research_test_chip"):
            tile_map_path = root / folder / "tile_simulation_map.json"
            try:
                tile_map = json.loads(tile_map_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                _fail(errors, f"{folder}: tile_simulation_map.json is missing or unreadable")
                tile_map = {}
            if tile_map.get("full_tile_solver_executed") is not True and (
                "PHYSICS_VERIFIED FOR THE FULL TILE" in upper
                or "FULL-TILE EM SOLVE EXECUTED" in upper
                or "FULL TILE SOLVER EXECUTED" in upper
            ):
                _fail(errors, f"{folder}: README overclaims a full tile-level solve")
        # A research-grade claim requires readback pass + stated limitations.
        readback = root / folder / "klayout_readback.json"
        try:
            readback_payload = json.loads(readback.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            readback_payload = {}
        if readback_payload.get("status") != "pass":
            _fail(errors, f"{folder}: showcased example without passing KLayout readback")
        example_readme = root / folder / "README.md"
        if example_readme.is_file():
            body = example_readme.read_text(encoding="utf-8")
            if "## Limitation" not in body:
                _fail(errors, f"{folder}: example README lacks a Limitation section")
            if "NOT_FABRICATION_READY" not in body:
                _fail(errors, f"{folder}: example README must state NOT_FABRICATION_READY")


def validate(readme: Path, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if not readme.is_file():
        return [f"README not found: {readme}"]
    text = readme.read_text(encoding="utf-8")
    _check_stale_claims(text, errors)
    _check_matrix(text, root, errors)
    _check_benchmark_table(text, root, errors)
    _check_showcase(text, root, errors)
    _check_showcase_paths(root, errors)
    _check_no_committed_absolute_paths(root, errors)
    _check_showcase_unit_language(root, errors)
    _check_tile_simulation_map_summary(root, errors)
    _check_showcase_table_formatting(text, errors)
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
