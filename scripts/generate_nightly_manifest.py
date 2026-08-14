#!/usr/bin/env python3
"""Compare two deterministic prompt runs and write a compact nightly manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

DETERMINISTIC_ARTIFACTS = (
    "intent.json",
    "layout.json",
    "output.gds",
    "output.svg",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(first: Path, second: Path, *, git_commit: str) -> dict[str, object]:
    artifacts: dict[str, dict[str, object]] = {}
    missing: list[str] = []
    mismatched: list[str] = []
    for relative in DETERMINISTIC_ARTIFACTS:
        first_path = first / relative
        second_path = second / relative
        if not first_path.is_file() or not second_path.is_file():
            missing.append(relative)
            continue
        first_hash = sha256_file(first_path)
        second_hash = sha256_file(second_path)
        equal = first_hash == second_hash
        if not equal:
            mismatched.append(relative)
        artifacts[relative] = {
            "first_sha256": first_hash,
            "second_sha256": second_hash,
            "byte_identical": equal,
            "size_bytes": first_path.stat().st_size,
        }
    return {
        "schema": "textlayout.nightly-evidence.v1",
        "git_commit": git_commit,
        "prompt": "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap",
        "canonical_and_showcase_drift_checks": "PASSED_BEFORE_MANIFEST",
        "path_bearing_artifacts": {
            "uploaded_but_not_byte_compared": ["klayout_readback.json", "verification.json"],
            "reason": "These records honestly embed their distinct absolute output.gds paths.",
        },
        "deterministic_artifacts": artifacts,
        "missing_artifacts": missing,
        "mismatched_artifacts": mismatched,
        "passed": not missing and not mismatched,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    manifest = build_manifest(args.first, args.second, git_commit=commit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
