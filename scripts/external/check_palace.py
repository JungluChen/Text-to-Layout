"""Check pinned Palace/Gmsh state without promoting downloads to installations."""

from __future__ import annotations

import argparse
import json

from _palace_common import (
    BENCHMARK_ROOT,
    CHECK_REPORT,
    GMESH_VERSION,
    PALACE_VERSION,
    SMOKE_ROOT,
    gmsh_identity,
    palace_install_identity,
    read_json,
    verify_palace_archive,
    write_json,
)


def _hash_validated_result(root, name: str) -> bool:
    payload = read_json(root / name)
    if payload is None:
        return False
    for relative, expected in payload.get("output_file_hashes", {}).items():
        from _palace_common import sha256_file

        path = root / relative
        if not path.is_file() or sha256_file(path) != expected:
            return False
    return bool(payload.get("solver_output_parsed"))


def _benchmark_valid() -> bool:
    from textlayout.evidence.canonical import load_canonical

    path = BENCHMARK_ROOT / "canonical_evidence.json"
    if not path.is_file():
        return False
    try:
        evidence = load_canonical(path)
    except (OSError, ValueError):
        return False
    return not evidence.verify_output_hashes(BENCHMARK_ROOT) and evidence.status.value in {
        "CONVERGENCE_FAILED",
        "SIMULATION_EXECUTED",
        "PHYSICS_VERIFIED",
    }


def check() -> dict[str, object]:
    archive = verify_palace_archive()
    installed = palace_install_identity()
    state = "ABSENT"
    if archive["available"]:
        state = "DOWNLOADED"
    if installed is not None:
        state = "INSTALLED"
    if installed is not None and _hash_validated_result(SMOKE_ROOT, "result.json"):
        state = "SMOKE_TEST_PASSED"
    if state == "SMOKE_TEST_PASSED" and _benchmark_valid():
        state = "BENCHMARK_EXECUTED"
    return {
        "schema": "textlayout.palace-check.v1",
        "state": state,
        "required_palace_version": PALACE_VERSION,
        "source_archive": archive,
        "installation": installed,
        "gmsh": gmsh_identity(),
        "gmsh_version_valid": gmsh_identity().get("version") == GMESH_VERSION,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-absent", action="store_true")
    args = parser.parse_args()
    payload = check()
    write_json(CHECK_REPORT, payload)
    print(json.dumps(payload, indent=2))
    return 0 if args.allow_absent or payload["state"] in {
        "INSTALLED",
        "SMOKE_TEST_PASSED",
        "BENCHMARK_EXECUTED",
    } else 1


if __name__ == "__main__":
    raise SystemExit(main())
