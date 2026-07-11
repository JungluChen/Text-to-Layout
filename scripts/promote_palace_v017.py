"""Promote a validated Palace 0.17 CPW run to the current benchmark reference.

    uv run python scripts/promote_palace_v017.py [--run out/palace_resonator_v017]

Promotion is refused unless every retained output hash re-verifies, the
solver version is exactly 0.17.0, and the evidence status is solver-backed
(``SIMULATION_EXECUTED``/``CONVERGENCE_FAILED``/``PHYSICS_VERIFIED``). On
success the ``current_reference_candidate`` entry in
``examples/solver_benchmarks/palace_cpw_quarter_wave/provenance.json`` is
filled in with the run's identity. The historical Palace 0.16 entry is never
touched.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from textlayout.evidence.canonical import load_canonical  # noqa: E402

PROVENANCE = (
    ROOT / "examples" / "solver_benchmarks" / "palace_cpw_quarter_wave" / "provenance.json"
)
SOLVER_BACKED = {"SIMULATION_EXECUTED", "CONVERGENCE_FAILED", "PHYSICS_VERIFIED"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default="out/palace_resonator_v017")
    args = parser.parse_args(argv)
    run = (ROOT / args.run).resolve()
    evidence_path = run / "canonical_evidence.json"
    if not evidence_path.is_file():
        print(f"[FAIL] no canonical evidence at {evidence_path}", file=sys.stderr)
        return 1
    evidence = load_canonical(evidence_path)
    problems: list[str] = []
    if evidence.solver_version != "0.17.0":
        problems.append(f"solver_version is {evidence.solver_version!r}, not 0.17.0")
    if evidence.status.value not in SOLVER_BACKED:
        problems.append(f"status {evidence.status.value} is not solver-backed")
    if not evidence.solver_executable_sha256:
        problems.append("solver executable SHA-256 is absent")
    if not evidence.command or evidence.return_code != 0:
        problems.append("no successful Palace process is recorded on the evidence")
    if not evidence.output_file_hashes:
        problems.append("evidence retains no output hashes")
    problems.extend(evidence.verify_output_hashes(run))
    if problems:
        for problem in problems:
            print(f"[FAIL] {problem}", file=sys.stderr)
        print("promotion refused; the Palace 0.16 record remains the reference.")
        return 1
    payload = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    candidate = next(
        entry for entry in payload["runs"] if entry["role"] == "current_reference_candidate"
    )
    candidate.update(
        {
            "role": "current_reference",
            "date": evidence.timestamp,
            "git_commit": evidence.git_commit,
            "evidence_id": evidence.evidence_id,
            "status": evidence.status.value,
            "notes": (
                "Promoted after every output hash and parser check passed. The Palace "
                "0.16 record above is preserved verbatim as the historical run."
            ),
        }
    )
    candidate["execution_identity"]["executable_sha256"] = evidence.solver_executable_sha256
    PROVENANCE.write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        f"promoted {evidence.evidence_id} ({evidence.status.value}, "
        f"{evidence.extracted_value} {evidence.extracted_unit}) to current reference"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
