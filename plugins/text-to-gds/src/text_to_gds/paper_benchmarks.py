"""Automatic, provenance-aware paper reproduction benchmark registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from text_to_gds.jtwpa import gaydamachenko_reference_config, jtwpa_reduced_3wm_gain, jtwpa_stop_bands
from text_to_gds.traveling_wave import planat_linear_gap


def _run_one(parameters: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    model = parameters["model"]
    if model == "planat_linear_gap":
        result = planat_linear_gap(parameters.get("parameters", {}).get("sample", "A"))
        computed = result["computed"]["gap_center_ghz"]
        target = float(expected["gap_center_ghz"])
        error = abs(computed - target) / target
        passed = error <= float(expected["gap_center_tolerance_fraction"])
        return {"status": "passed" if passed else "failed", "computed": {"gap_center_ghz": computed}, "expected": expected, "relative_error": error}
    if model == "gaydamachenko_tmm":
        config = gaydamachenko_reference_config(
            pump_frequency_ghz=float(parameters["parameters"]["pump_frequency_ghz"])
        )
        gain = jtwpa_reduced_3wm_gain(config)
        bands = jtwpa_stop_bands(config)
        coherence_error = abs(gain["coherence_length_cells_at_6p7ghz"] - expected["coherence_length_cells"]) / expected["coherence_length_cells"]
        checks = {
            "coherence": coherence_error <= expected["coherence_tolerance_fraction"],
            "gain": gain["gain_3_to_9_ghz"]["minimum_db"] >= expected["minimum_gain_3_to_9_ghz_db"],
            "second_harmonic_gap": bands[1]["lower_ghz"] < 2.0 * config.pump_frequency_ghz < bands[1]["upper_ghz"],
        }
        return {"status": "passed" if all(checks.values()) else "failed", "checks": checks, "computed": {"coherence_length_cells": gain["coherence_length_cells_at_6p7ghz"], "minimum_gain_3_to_9_ghz_db": gain["gain_3_to_9_ghz"]["minimum_db"]}, "expected": expected}
    return {
        "status": "skipped",
        "reason": expected.get("reason", f"Required backend: {parameters.get('required_backend')}"),
        "expected": expected,
    }


def run_paper_benchmark_suite(root: str | Path, *, report_path: str | Path) -> dict[str, Any]:
    benchmark_root = Path(root)
    results = []
    for directory in sorted(path for path in benchmark_root.iterdir() if path.is_dir()):
        parameters = json.loads((directory / "paper_parameters.yaml").read_text(encoding="utf-8"))
        expected = json.loads((directory / "expected_results.json").read_text(encoding="utf-8"))
        result = _run_one(parameters, expected)
        results.append({"paper_id": parameters["paper_id"], "title": parameters["title"], **result})
    counts = {status: sum(item["status"] == status for item in results) for status in ("passed", "failed", "skipped")}
    report = {
        "schema": "text-to-gds.paper-benchmark-suite.v1",
        "status": "passed" if counts["failed"] == 0 and counts["passed"] > 0 else "failed",
        "counts": counts,
        "results": results,
        "coverage_fraction": float(np.mean([item["status"] == "passed" for item in results])) if results else 0.0,
    }
    output = Path(report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(output)
    return report
