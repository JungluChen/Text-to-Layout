"""40-qubit synthetic chip collision-yield showcase (Sprint 4).

SYNTHETIC_EXAMPLE / ANALYTICAL_ONLY / NOT_FABRICATION_READY: every number is
an illustrative statistical model — no solver, no foundry data, no measured
hardware. What this demonstrates is the *closed loop*:

    load lattice (examples/chip_lattices/40q_synthetic.yaml)
      -> nominal collision analysis + seeded Monte Carlo yield
      -> greedy frequency retune proposal
      -> Monte Carlo yield of the retuned plan
      -> evidence under out/evidence/

Run:
    uv run python examples/07_40q_chip_collision_yield.py [--out out/evidence]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from textlayout.chip_lattice import (
    QubitLattice,
    optimize_frequencies,
    run_chip_collision_yield,
    write_chip_optimize_report,
    write_chip_yield_report,
)

ROOT = Path(__file__).resolve().parents[1]
LATTICE_YAML = ROOT / "examples" / "chip_lattices" / "40q_synthetic.yaml"
SEED = 1234
N_SAMPLES = 400


def apply_retunes(lattice: QubitLattice, proposals) -> QubitLattice:
    """Return a copy of ``lattice`` with the proposed target frequencies."""
    retuned = {p.qubit_id: p.proposed_freq_ghz for p in proposals}
    nodes = [
        node.model_copy(update={"target_freq_ghz": retuned[node.qubit_id]})
        if node.qubit_id in retuned
        else node
        for node in lattice.nodes
    ]
    return lattice.model_copy(update={"nodes": nodes, "name": lattice.name + "_retuned"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ROOT / "out" / "evidence"))
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--n-samples", type=int, default=N_SAMPLES)
    args = parser.parse_args(argv)
    out = Path(args.out)

    lattice = QubitLattice.model_validate(
        yaml.safe_load(LATTICE_YAML.read_text(encoding="utf-8"))
    )

    baseline = run_chip_collision_yield(lattice, n_samples=args.n_samples, seed=args.seed)
    files = write_chip_yield_report(baseline, out)

    optimized = optimize_frequencies(lattice, max_retune_mhz=300.0)
    files.update(write_chip_optimize_report(optimized, out))

    retuned_yield = None
    if optimized.proposals:
        retuned = apply_retunes(lattice, optimized.proposals)
        retuned_yield = run_chip_collision_yield(
            retuned, n_samples=args.n_samples, seed=args.seed
        )

    summary = {
        "status": "SYNTHETIC_EXAMPLE",
        "fabrication_readiness": "NOT_FABRICATION_READY",
        "lattice": lattice.name,
        "seed": args.seed,
        "n_samples": args.n_samples,
        "baseline": {
            "nominal_violations": baseline.nominal_report.n_violations,
            "collision_free_yield_pct": baseline.collision_free_pct,
            "top_risky_pairs": [
                {
                    "pair": f"{p.node_a}-{p.node_b}",
                    "rule": p.rule,
                    "probability": p.collision_probability,
                }
                for p in baseline.risky_pairs[:10]
            ],
        },
        "retune": {
            "violations_before": optimized.before.n_violations,
            "violations_after": optimized.after.n_violations,
            "converged": optimized.converged,
            "n_proposals": len(optimized.proposals),
        },
        "retuned_collision_free_yield_pct": (
            retuned_yield.collision_free_pct if retuned_yield else None
        ),
        "files": files,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
