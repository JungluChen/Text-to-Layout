"""Check that retained native evidence supports only the claims made for it."""

import hashlib
import json
from pathlib import Path


def test_fasthenry_packet_retains_inputs_and_does_not_certify_convergence() -> None:
    root = Path(__file__).resolve().parents[2]
    packet = json.loads(
        (root / "docs/verification/evidence/fasthenry_real_run.json").read_text(
            encoding="utf-8"
        )
    )
    assert packet["summary"]["all_runs_succeeded"] is True
    assert packet["summary"]["mesh_convergence_verified"] is False
    assert "not converged" in packet["summary"]["convergence_limitations"]
    for benchmark in packet["benchmarks"].values():
        for refinement in benchmark["refinements"]:
            assert hashlib.sha256(refinement["input_deck"].encode()).hexdigest() == (
                refinement["input_deck_sha256"]
            )
            assert hashlib.sha256(refinement["zc_matrix_raw"].encode()).hexdigest() == (
                refinement["zc_matrix_sha256"]
            )
            assert refinement["stdout"]
            assert refinement["exit_code"] == 0

    spiral = packet["benchmarks"]["four_turn_square_spiral"]["refinements"]
    assert abs(spiral[1]["mesh_refinement_delta_l_pct"]) > 0.05
