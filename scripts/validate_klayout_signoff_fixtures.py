"""Validate committed KLayout DRC and partial-LVS fixtures into audit JSON."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from textlayout.pdk.klayout_drc import run_drc, to_lydrc
from textlayout.pdk.loader import load_pdk
from textlayout.pdk.lvs import run_partial_connectivity_lvs

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "out" / "audit"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_head() -> str:
    import subprocess

    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()


def validate_drc() -> dict[str, Any]:
    fixture_root = REPO / "tests" / "fixtures" / "klayout_drc"
    manifest = json.loads((fixture_root / "expectations.json").read_text(encoding="ascii"))
    pdk = load_pdk(REPO / manifest["pdk"])
    runset = to_lydrc(pdk)
    runset_hash = hashlib.sha256(runset.encode("utf-8")).hexdigest()
    rows = []
    all_passed = runset_hash == manifest["runset_hash"]
    for fixture in manifest["fixtures"]:
        start = time.perf_counter()
        gds = REPO / fixture["path"]
        report = run_drc(pdk, gds, top_cell=fixture["top_cell"])
        observed = sorted({violation.rule_id for violation in report.violations})
        expected = sorted(fixture["expected_rule_ids"])
        unexpected = sorted(set(observed) - set(expected))
        passed = (
            sha256(gds) == fixture["gds_hash"]
            and set(expected) <= set(observed)
            and len(unexpected) <= fixture["max_unexpected_violations"]
            and (
                bool(expected)
                or not report.violations
            )
        )
        all_passed = all_passed and passed
        rows.append(
            {
                "fixture": fixture["name"],
                "status": "passed" if passed else "failed",
                "input_gds_sha256": sha256(gds),
                "top_cell": fixture["top_cell"],
                "expected_rule_ids": expected,
                "observed_rule_ids": observed,
                "unexpected_violations": unexpected,
                "violation_count": len(report.violations),
                "runtime_seconds": round(time.perf_counter() - start, 6),
            }
        )
    return {
        "schema": "textlayout.klayout-drc-fixture-validation.v1",
        "status": "PDK_DRC_FIXTURES_VALIDATED" if all_passed else "FAILED",
        "source_git_commit": git_head(),
        "execution_mode": "local_klayout_python_region_engine",
        "containerized": False,
        "pdk_hash": manifest["pdk_hash"],
        "generated_runset_hash": runset_hash,
        "manifest_runset_hash": manifest["runset_hash"],
        "total_rules": len({rule for row in rows for rule in row["observed_rule_ids"] + row["expected_rule_ids"]}),
        "supported_rules": [],
        "unsupported_rules": report.unsupported_rules if manifest["fixtures"] else [],
        "fixture_expectations_passed": all_passed,
        "fixtures": rows,
    }


def validate_lvs() -> dict[str, Any]:
    fixture_root = REPO / "tests" / "fixtures" / "klayout_lvs"
    manifest = json.loads((fixture_root / "expectations.json").read_text(encoding="ascii"))
    rows = []
    all_passed = True
    supported: set[str] = set()
    for fixture in manifest["fixtures"]:
        start = time.perf_counter()
        gds = REPO / fixture["path"]
        report = run_partial_connectivity_lvs(
            gds,
            reference_nets=fixture["reference_nets"],
            conductor_layers={
                name: tuple(values) for name, values in fixture["conductor_layers"].items()
            },
            terminal_layer=tuple(fixture["terminal_layer"]),
            supported_structures=fixture["supported_structures"],
            unsupported_structures=manifest["unsupported_structures"],
            unsupported_devices=manifest["unsupported_devices"],
            top_cell=fixture["top_cell"],
        )
        supported.update(fixture["supported_structures"])
        observed_errors = _lvs_errors(report)
        expected_errors = sorted(fixture["expected_errors"])
        passed = (
            sha256(gds) == fixture["gds_hash"]
            and set(expected_errors) <= set(observed_errors)
            and (bool(expected_errors) or report["passed"])
        )
        all_passed = all_passed and passed
        rows.append(
            {
                "fixture": fixture["name"],
                "status": "passed" if passed else "failed",
                "input_gds_sha256": sha256(gds),
                "top_cell": fixture["top_cell"],
                "expected_errors": expected_errors,
                "observed_errors": observed_errors,
                "reference_nets": report["reference_nets"],
                "extracted_nets": report["extracted_nets"],
                "opens": report["opens"],
                "shorts": report["shorts"],
                "floating_nets": report["floating_nets"],
                "missing_terminals": report["missing_terminals"],
                "terminal_mismatches": report["terminal_mismatches"],
                "runtime_seconds": round(time.perf_counter() - start, 6),
            }
        )
    return {
        "schema": "textlayout.klayout-partial-lvs-fixture-validation.v1",
        "status": "KLAYOUT_PARTIAL_LVS_FIXTURES_VALIDATED" if all_passed else "FAILED",
        "source_git_commit": git_head(),
        "execution_mode": "local_klayout_python_geometry_extraction",
        "containerized": False,
        "scope": "connectivity_partial_lvs",
        "supported_structures": sorted(supported),
        "unsupported_structures": manifest["unsupported_structures"],
        "unsupported_devices": manifest["unsupported_devices"],
        "fixture_expectations_passed": all_passed,
        "full_lvs_pass": False,
        "fixtures": rows,
    }


def _lvs_errors(report: dict[str, Any]) -> list[str]:
    errors = []
    if report["opens"]:
        errors.append("OPEN")
    if report["shorts"]:
        errors.append("SHORT")
    if report["floating_nets"]:
        errors.append("FLOATING_NET")
    if report["missing_terminals"]:
        errors.append("MISSING_TERMINAL")
    if report["extra_terminals"]:
        errors.append("EXTRA_TERMINAL")
    if report["terminal_mismatches"]:
        errors.append("TERMINAL_MISMATCH")
    return sorted(errors)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    drc = validate_drc()
    lvs = validate_lvs()
    (OUT / "klayout_drc_fixtures.json").write_text(
        json.dumps(drc, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "klayout_partial_electrical_lvs.json").write_text(
        json.dumps(lvs, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if drc["fixture_expectations_passed"] and lvs["fixture_expectations_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
