"""Seeded Monte Carlo collision-yield analysis across a qubit lattice.

Each Monte Carlo sample draws one frequency per node, independently, from
``N(target_freq_ghz, freq_sigma_mhz)`` — ``freq_sigma_mhz`` is the node's own
input (typically produced upstream by :mod:`textlayout.yield_model` from JJ
process variation) so this module stays decoupled from how that spread was
derived. Readout and coupler frequencies are treated as fixed (not resampled)
— a simplification stated explicitly in every result's assumptions list.

A chip sample is collision-free only if every rule in
:func:`textlayout.chip_lattice.collision.evaluate_collisions` passes for that
sample's frequency draw. Risky pairs are ranked by how often each specific
(node_a, node_b, rule) triple is the one that fails.
"""

from __future__ import annotations

import math
from collections import Counter

import numpy as np

from textlayout.chip_lattice.collision import analyze_nominal, evaluate_collisions
from textlayout.chip_lattice.models import ChipYieldResult, QubitLattice, RiskyPair


def _wilson_ci95(successes: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    z = 1.959963984540054
    phat = successes / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    lower = max(0.0, center - half)
    upper = min(1.0, center + half)
    return (lower * 100.0 if lower > 1e-12 else 0.0, upper * 100.0 if upper < 1 - 1e-12 else 100.0)


def run_chip_collision_yield(
    lattice: QubitLattice, *, n_samples: int = 2000, seed: int = 1234
) -> ChipYieldResult:
    """Monte Carlo probability that ``lattice`` is collision-free end to end."""
    if n_samples < 100:
        raise ValueError("need at least 100 samples for a meaningful yield estimate")
    rng = np.random.default_rng(seed)

    node_ids = [node.qubit_id for node in lattice.nodes]
    means = np.array([node.target_freq_ghz for node in lattice.nodes])
    sigmas_ghz = np.array([node.freq_sigma_mhz / 1e3 for node in lattice.nodes])

    passes = 0
    pair_failures: Counter[tuple[str, str, str]] = Counter()
    pair_totals: Counter[tuple[str, str, str]] = Counter()

    for _ in range(n_samples):
        draw = rng.normal(means, sigmas_ghz)
        frequencies = dict(zip(node_ids, draw, strict=True))
        findings = evaluate_collisions(lattice, frequencies)
        sample_ok = True
        for finding in findings:
            key = (finding.node_a, finding.node_b, finding.rule)
            pair_totals[key] += 1
            if finding.violated:
                pair_failures[key] += 1
                sample_ok = False
        if sample_ok:
            passes += 1

    risky_pairs = sorted(
        (
            RiskyPair(
                node_a=node_a, node_b=node_b, rule=rule,
                collision_probability=pair_failures[(node_a, node_b, rule)] / n_samples,
            )
            for (node_a, node_b, rule) in pair_totals
            if pair_failures[(node_a, node_b, rule)] > 0
        ),
        key=lambda pair: pair.collision_probability,
        reverse=True,
    )

    return ChipYieldResult(
        lattice_name=lattice.name,
        n_samples=n_samples,
        seed=seed,
        collision_free_pct=passes / n_samples * 100.0,
        collision_free_ci95_pct=_wilson_ci95(passes, n_samples),
        risky_pairs=risky_pairs,
        nominal_report=analyze_nominal(lattice),
        assumptions=[
            "Each node's frequency is drawn independently from "
            "N(target_freq_ghz, freq_sigma_mhz); freq_sigma_mhz is an input, "
            "typically produced upstream by textlayout.yield_model.",
            "Readout and coupler frequencies are treated as FIXED (not resampled).",
            "A chip sample passes only if every collision rule holds for every "
            "edge/node simultaneously.",
            "No correlated wafer-common factor across nodes in this module — "
            "if that correlation matters, derive freq_sigma_mhz including it "
            "upstream before calling this analysis.",
        ],
        provenance={
            "engine": "textlayout.chip_lattice.monte_carlo",
            "sampling": "numpy.random.default_rng",
        },
        synthetic=True,
    )
