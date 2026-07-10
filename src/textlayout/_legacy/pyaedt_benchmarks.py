"""Solver-gated HFSS/Q3D qualification benchmark registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def _nested_value(payload: dict[str, Any], key: str) -> float:
    value: Any = payload
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(key)
        value = value[part]
    return float(value)


def run_pyaedt_benchmark_suite(
    root: str | Path,
    *,
    report_path: str | Path,
    results_root: str | Path | None = None,
) -> dict[str, Any]:
    """Compare licensed-solver result JSON with registered HFSS/Q3D targets."""
    benchmark_root = Path(root)
    solver_results = Path(results_root) if results_root else benchmark_root / "results"
    results = []
    for directory in sorted(path for path in benchmark_root.iterdir() if path.is_dir()):
        definition_path = directory / "paper.yaml"
        if not definition_path.exists():
            continue
        definition = yaml.safe_load(definition_path.read_text(encoding="utf-8"))
        benchmark_id = str(definition["benchmark_id"])
        result_path = solver_results / f"{benchmark_id}.result.json"
        if not result_path.exists():
            results.append(
                {
                    "benchmark_id": benchmark_id,
                    "status": "skipped",
                    "reason": "Licensed PyAEDT solver result is not present.",
                    "expected_result_path": str(result_path),
                }
            )
            continue
        solver_result = json.loads(result_path.read_text(encoding="utf-8"))
        checks = []
        for metric in definition["metrics"]:
            target = float(metric["target"])
            actual = _nested_value(solver_result, str(metric["result_key"]))
            relative_error = abs(actual - target) / max(abs(target), 1e-30)
            tolerance = float(metric["tolerance_fraction"])
            checks.append(
                {
                    "name": metric["name"],
                    "target": target,
                    "actual": actual,
                    "unit": metric["unit"],
                    "relative_error": relative_error,
                    "tolerance_fraction": tolerance,
                    "passed": relative_error <= tolerance,
                }
            )
        results.append(
            {
                "benchmark_id": benchmark_id,
                "status": "passed" if all(check["passed"] for check in checks) else "failed",
                "solver_result_path": str(result_path),
                "checks": checks,
            }
        )
    counts = {
        status: sum(item["status"] == status for item in results)
        for status in ("passed", "failed", "skipped")
    }
    report = {
        "schema": "text-to-gds.pyaedt-benchmark-suite.v1",
        "status": "failed" if counts["failed"] else ("passed" if counts["passed"] else "prepared"),
        "counts": counts,
        "results": results,
        "validity": (
            "Skipped entries are not passes. Store licensed AEDT outputs under the reported result paths."
        ),
    }
    output = Path(report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(output)
    return report
