"""Re-derive canonical evidence for every showcase from its committed outputs.

    uv run python scripts/build_canonical_evidence.py [--check]

No solver is re-run. Each showcase's recorded solver output is re-parsed with
the current parser, the value is recomputed, the convergence criterion the
solver actually enforced is read back, and the status is computed.

`--check` fails instead of writing, so CI can detect a canonical record that no
longer matches the outputs it claims to describe.

Regeneration is deterministic: the timestamp is carried over from the committed
record whenever nothing else about the evidence changed, so re-running this
script never dirties the tree on its own.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from textlayout.evidence.build import RECIPES, build_canonical  # noqa: E402
from textlayout.evidence.canonical import (  # noqa: E402
    CanonicalEvidence,
    sha256_json,
    write_canonical,
)
from textlayout.evidence.consistency import canonical_path  # noqa: E402


def _fingerprint(record: CanonicalEvidence) -> str:
    """Content hash of everything except the timestamp."""
    payload = record.to_dict()
    payload.pop("timestamp", None)
    return sha256_json(payload)


def _content_fingerprint(record: CanonicalEvidence) -> str:
    """Hash evidence content while excluding stable audit metadata."""
    payload = record.to_dict()
    for key in (
        "timestamp",
        "git_commit",
        "environment_hash",
        "evidence_generation_environment_hash",
        "evidence_generation_git_commit",
        "evidence_generated_at",
    ):
        payload.pop(key, None)
    return sha256_json(payload)


def _stabilised(fresh: CanonicalEvidence, existing_path: Path) -> CanonicalEvidence:
    """Carry stable metadata over when content evidence is unchanged.

    A release check may run after a test that intentionally hides ``git`` from
    PATH. In that case ``build_canonical`` cannot re-query the source commit,
    but the design/input/output hashes still establish whether the evidence
    changed. Preserve the previously recorded commit instead of manufacturing
    a false stale-record failure.
    """
    if not existing_path.is_file():
        return fresh
    try:
        previous = json.loads(existing_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fresh
    stamp = previous.get("timestamp")
    if not isinstance(stamp, str):
        return fresh
    try:
        previous_record = CanonicalEvidence.model_validate(
            {k: v for k, v in previous.items() if k != "confidence_class"}
        )
    except ValueError:
        return fresh
    if _content_fingerprint(previous_record) != _content_fingerprint(fresh):
        return fresh

    updates: dict[str, str | None] = {"timestamp": stamp}
    for key in (
        "git_commit",
        "environment_hash",
        "evidence_generation_environment_hash",
        "evidence_generation_git_commit",
        "evidence_generated_at",
        "solver_execution_environment_hash",
        "solver_execution_git_commit",
        "solver_executable_sha256",
        "solver_container_digest",
        "solver_executed_at",
        "container_digest",
    ):
        previous_value = previous.get(key)
        if isinstance(previous_value, str) or previous_value is None:
            updates[key] = previous_value
    candidate = fresh.model_copy(update=updates)
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Fail if any committed record is out of date."
    )
    args = parser.parse_args(argv)

    stale: list[str] = []
    for showcase_id in sorted(RECIPES):
        showcase = ROOT / "examples" / "showcase" / showcase_id
        target = canonical_path(showcase)
        record = _stabilised(build_canonical(showcase, ROOT), target)

        if args.check:
            if not target.is_file():
                stale.append(f"{showcase_id}: no canonical record")
                continue
            committed = json.loads(target.read_text(encoding="utf-8"))
            if committed != record.to_dict():
                stale.append(
                    f"{showcase_id}: canonical record disagrees with a fresh derivation "
                    f"from its committed solver outputs"
                )
            continue

        write_canonical(record, target)
        conv = record.convergence.converged if record.convergence else None
        print(
            f"{showcase_id:34} {record.status.value:22} "
            f"value={record.extracted_value!r} converged={conv}"
        )

    if args.check:
        for problem in stale:
            print(f"::error::{problem}")
        if stale:
            print(f"\n{len(stale)} canonical record(s) are stale. "
                  "Run scripts/build_canonical_evidence.py and commit.")
            return 1
        print(f"{len(RECIPES)}/{len(RECIPES)} canonical records are current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
