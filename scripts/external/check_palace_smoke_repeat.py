"""Compare two retained official Palace smoke runs; repeatability is not convergence."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

from _palace_common import PALACE_COMMIT, PALACE_VERSION, sha256_file
from textlayout.solvers.palace.parser import parse_eigenmodes

RELATIVE_DRIFT_LIMIT = 1e-6


def retained_run(root: Path) -> tuple[dict, list[int], list[float]]:
    report = json.loads((root / "result.json").read_text(encoding="utf-8"))
    if report.get("status") != "SMOKE_TEST_PASSED" or report.get("return_code") != 0:
        raise ValueError("both runs must have completed the official smoke successfully")
    if (
        report.get("palace_version") != PALACE_VERSION
        or report.get("palace_commit") != PALACE_COMMIT
    ):
        raise ValueError("unexpected Palace source identity")
    if not re.fullmatch(r"[0-9a-f]{64}", report.get("palace_executable_sha256", "")):
        raise ValueError("missing executable SHA-256")
    for section in ("input_file_hashes", "output_file_hashes"):
        hashes = report.get(section)
        if not isinstance(hashes, dict) or not hashes:
            raise ValueError(f"missing {section}")
        for relative, expected in hashes.items():
            path = (root / relative).resolve()
            if not path.is_relative_to(root.resolve()) or sha256_file(path) != expected:
                raise ValueError(f"retained artifact mismatch: {relative}")
    eigenvalues = root / "postpro/eigenmode/eig.csv"
    if "postpro/eigenmode/eig.csv" not in report["output_file_hashes"]:
        raise ValueError("eigenvalue output is not hash-bound")
    modes = parse_eigenmodes(eigenvalues)
    if len({mode.index for mode in modes}) != len(modes):
        raise ValueError("duplicate eigenmode indices")
    ordered = sorted(modes, key=lambda mode: mode.index)
    indices = [mode.index for mode in ordered]
    values = [mode.frequency_ghz for mode in ordered]
    if not values or any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("invalid eigenfrequencies")
    return report, indices, values


def compare(first: Path, repeat: Path) -> dict:
    if first.resolve() == repeat.resolve():
        raise ValueError("two distinct retained run directories are required")
    left, indices, frequencies = retained_run(first)
    right, repeat_indices, repeated = retained_run(repeat)
    for key in ("palace_executable_sha256", "input_file_hashes"):
        if left[key] != right[key]:
            raise ValueError(f"repeat changed {key}")
    if indices != repeat_indices:
        raise ValueError("repeat changed mode indices/count")
    drifts = [abs(b - a) / a for a, b in zip(frequencies, repeated, strict=True)]
    passed = all(value < RELATIVE_DRIFT_LIMIT for value in drifts)
    return {
        "schema": "textlayout.palace-smoke-repeat.v1",
        "status": "REPEATABLE_SMOKE" if passed else "REPEATABILITY_FAILED",
        "passed": passed,
        "relative_frequency_drifts": drifts,
        "strict_relative_drift_limit": RELATIVE_DRIFT_LIMIT,
        "palace_executable_sha256": left["palace_executable_sha256"],
        "first_result_sha256": sha256_file(first / "result.json"),
        "repeat_result_sha256": sha256_file(repeat / "result.json"),
        "scope": "same-input official smoke repeatability; not mesh convergence or physics verification",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--repeat", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output already exists; preserve prior comparison evidence")
    try:
        result = compare(args.first, args.repeat)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result = {
            "schema": "textlayout.palace-smoke-repeat.v1",
            "passed": False,
            "status": "INVALID_EVIDENCE",
            "error": str(exc),
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
