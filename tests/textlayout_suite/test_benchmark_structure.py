"""README benchmark artifact and honesty-contract tests."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
BENCHMARKS = ROOT / "examples" / "benchmarks"


def test_ready_benchmarks_have_complete_packets() -> None:
    required = {
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
    for folder in sorted(BENCHMARKS.iterdir()):
        spec = json.loads((folder / "layout.json").read_text(encoding="utf-8"))
        if spec.get("metadata", {}).get("benchmark_status") != "ready":
            continue
        assert required <= {path.name for path in folder.iterdir()}, folder.name
        verification = json.loads((folder / "verification.json").read_text(encoding="utf-8"))
        assert verification["status"] == "pass", folder.name
        assert verification["warnings"], folder.name
        assert all((folder / name).stat().st_size > 0 for name in required)


def test_todo_benchmarks_do_not_claim_geometry_outputs() -> None:
    for folder in sorted(BENCHMARKS.iterdir()):
        spec = json.loads((folder / "layout.json").read_text(encoding="utf-8"))
        if spec.get("metadata", {}).get("benchmark_status") != "todo":
            continue
        assert not list(folder.glob("output.*")), folder.name
        assert (folder / "TODO.md").is_file()
        verification = json.loads((folder / "verification.json").read_text(encoding="utf-8"))
        assert verification["status"] == "todo"


def test_readme_references_every_ready_preview() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for folder in sorted(BENCHMARKS.iterdir()):
        spec = json.loads((folder / "layout.json").read_text(encoding="utf-8"))
        if spec.get("metadata", {}).get("benchmark_status") == "ready":
            assert f"examples/benchmarks/{folder.name}/output.png" in readme


def test_benchmark_checker_passes() -> None:
    import subprocess
    import sys

    completed = subprocess.run(
        [sys.executable, "scripts/check_benchmarks.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
