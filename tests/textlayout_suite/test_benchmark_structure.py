"""README benchmark artifact and honesty-contract tests."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
BENCHMARKS = ROOT / "examples" / "benchmarks"


def test_ready_idc_benchmark_has_complete_packet() -> None:
    folder = BENCHMARKS / "01_idc_0p6pf"
    required = {
        "prompt.md",
        "layout.json",
        "output.svg",
        "output.png",
        "output.gds",
        "output.json",
        "verification.json",
        "evidence.md",
        "report.md",
    }
    assert required <= {path.name for path in folder.iterdir()}
    verification = json.loads((folder / "verification.json").read_text(encoding="utf-8"))
    assert verification["status"] == "pass"
    assert verification["warnings"]
    assert all((folder / name).stat().st_size > 0 for name in required)


def test_todo_benchmarks_do_not_claim_geometry_outputs() -> None:
    for folder in sorted(BENCHMARKS.iterdir()):
        spec = json.loads((folder / "layout.json").read_text(encoding="utf-8"))
        if spec.get("metadata", {}).get("benchmark_status") != "todo":
            continue
        assert not list(folder.glob("output.*")), folder.name
        verification = json.loads((folder / "verification.json").read_text(encoding="utf-8"))
        assert verification["status"] == "todo"


def test_readme_references_ready_preview() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "examples/benchmarks/01_idc_0p6pf/output.png" in readme
