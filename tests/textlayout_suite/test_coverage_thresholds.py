from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_coverage_thresholds.py"


def _module():
    spec = importlib.util.spec_from_file_location("check_coverage_thresholds", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _payload(*, line: int = 90, branch: int = 80):
    return {
        "totals": {
            "covered_lines": line,
            "num_statements": 100,
            "covered_branches": branch,
            "num_branches": 100,
        },
        "files": {
            "src/textlayout/signoff.py": {
                "summary": {
                    "covered_lines": line,
                    "num_statements": 100,
                    "covered_branches": branch,
                    "num_branches": 100,
                }
            }
        },
    }


def test_global_and_changed_critical_thresholds_pass() -> None:
    module = _module()
    assert module.evaluate(_payload(), changed_files=["src/textlayout/signoff.py"]) == []


def test_global_line_and_branch_failures_are_distinct() -> None:
    module = _module()
    problems = module.evaluate(_payload(line=77, branch=59), changed_files=[])
    assert any("product line coverage" in problem for problem in problems)
    assert any("product branch coverage" in problem for problem in problems)


def test_legacy_data_and_uncovered_changed_critical_module_fail() -> None:
    module = _module()
    payload = _payload()
    payload["files"]["src/textlayout/_legacy/old.py"] = payload["files"][
        "src/textlayout/signoff.py"
    ]
    problems = module.evaluate(
        payload, changed_files=["src/textlayout/evidence/agreement.py"]
    )
    assert any("frozen legacy" in problem for problem in problems)
    assert any("absent from coverage" in problem for problem in problems)
