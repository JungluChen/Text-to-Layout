"""Greedy target-frequency retuning to reduce chip-level collisions.

This operates on the *frequency allocation plan* — which target frequency
each qubit is assigned during design, before fabrication — not on a
fabricated device. Retuning a fixed-frequency transmon after fabrication is
not generally possible; what IS a real, standard practice is choosing a
frequency allocation (a "binning" plan) across the lattice that avoids
collisions given the process's achievable frequency range. That is exactly
what this optimizer searches over, bounded by ``max_retune_mhz`` — the
fabrication constraint that a qubit can only be placed within a limited
frequency window of its originally planned target (representing, e.g., the
Jc range a process can reliably hit).

Algorithm: deterministic greedy coordinate descent on a *continuous* penalty
— the sum, over all violated rules, of how far short of the minimum
detuning each one falls (``max(0, min_required_mhz - detuning_mhz)``). A
binary violation *count* has no gradient: a step that narrows a violation
from "10 MHz short" to "5 MHz short" looks identical to "no improvement" if
you only count violations. The continuous penalty fixes that — every step
toward compliance is visible and rewarded, not just the step that finally
crosses the threshold.

At each iteration: find the node with the largest attributed penalty; try
moving it by ±step_mhz (bounded by ``max_retune_mhz`` from its *original*
target); keep the move only if it strictly reduces total penalty. Stop when
collision-free, no move improves the penalty, or the iteration budget is
exhausted. This is a local search, not a global optimum — deterministic (no
RNG) and always reports both before/after collision reports for auditability.
"""

from __future__ import annotations

from collections import defaultdict

from textlayout.chip_lattice.collision import analyze_nominal
from textlayout.chip_lattice.models import (
    ChipCollisionReport,
    ChipOptimizeResult,
    QubitLattice,
    RetuneProposal,
)

_DEFAULT_MAX_ITERATIONS = 400
_DEFAULT_STEP_MHZ = 5.0


def _total_penalty_mhz(report: ChipCollisionReport) -> float:
    return sum(
        max(0.0, finding.min_required_mhz - finding.detuning_mhz)
        for finding in report.findings
        if finding.violated
    )


def _penalty_by_node(lattice: QubitLattice, report: ChipCollisionReport) -> dict[str, float]:
    """Attribute each violation's shortfall to the real qubit node(s) involved."""
    known_ids = {node.qubit_id for node in lattice.nodes}
    penalties: dict[str, float] = defaultdict(float)
    for finding in report.findings:
        if not finding.violated:
            continue
        shortfall = finding.min_required_mhz - finding.detuning_mhz
        for node_id in (finding.node_a, finding.node_b):
            if node_id in known_ids:
                penalties[node_id] += shortfall
    return dict(penalties)


def _with_node_frequency(lattice: QubitLattice, qubit_id: str, new_freq_ghz: float) -> QubitLattice:
    new_nodes = [
        node.model_copy(update={"target_freq_ghz": new_freq_ghz})
        if node.qubit_id == qubit_id
        else node
        for node in lattice.nodes
    ]
    return lattice.model_copy(update={"nodes": new_nodes})


def optimize_frequencies(
    lattice: QubitLattice,
    *,
    max_retune_mhz: float = 300.0,
    step_mhz: float = _DEFAULT_STEP_MHZ,
    max_iterations: int = _DEFAULT_MAX_ITERATIONS,
) -> ChipOptimizeResult:
    """Greedily retune target frequencies to reduce (ideally eliminate) collisions."""
    before = analyze_nominal(lattice)
    if before.collision_free:
        return ChipOptimizeResult(
            lattice_name=lattice.name,
            before=before,
            after=before,
            proposals=[],
            iterations=0,
            converged=True,
            assumptions=["Lattice was already collision-free at nominal frequencies."],
        )

    original_freqs = {node.qubit_id: node.target_freq_ghz for node in lattice.nodes}
    current = lattice
    proposals: list[RetuneProposal] = []
    iterations = 0
    converged = False

    for iterations in range(1, max_iterations + 1):
        current_report = analyze_nominal(current)
        current_penalty = _total_penalty_mhz(current_report)
        if current_penalty <= 0.0:
            converged = True
            break

        penalties = _penalty_by_node(current, current_report)
        if not penalties:
            break  # violations exist only on synthetic readout/coupler ids; cannot retune those
        target_qubit_id = max(penalties, key=lambda qid: penalties[qid])
        target_node = current.node(target_qubit_id)
        original = original_freqs[target_qubit_id]

        best_candidate: QubitLattice | None = None
        best_penalty = current_penalty
        best_freq = target_node.target_freq_ghz
        for direction in (+1.0, -1.0):
            candidate_freq = target_node.target_freq_ghz + direction * step_mhz / 1e3
            if abs((candidate_freq - original) * 1e3) > max_retune_mhz:
                continue
            candidate_lattice = _with_node_frequency(current, target_qubit_id, candidate_freq)
            candidate_penalty = _total_penalty_mhz(analyze_nominal(candidate_lattice))
            if candidate_penalty < best_penalty - 1e-9:
                best_penalty = candidate_penalty
                best_candidate = candidate_lattice
                best_freq = candidate_freq

        if best_candidate is None:
            break  # no single-step move on the worst node improves the penalty; stop

        current = best_candidate
        proposals.append(
            RetuneProposal(
                qubit_id=target_qubit_id,
                original_freq_ghz=target_node.target_freq_ghz,
                proposed_freq_ghz=best_freq,
                reason=f"reduced total shortfall {current_penalty:.2f} -> {best_penalty:.2f} MHz",
            )
        )

    after = analyze_nominal(current)
    if after.collision_free:
        converged = True

    # Collapse proposals per qubit into one net (original -> final) statement.
    net_by_qubit: dict[str, RetuneProposal] = {}
    for proposal in proposals:
        original = original_freqs[proposal.qubit_id]
        net_by_qubit[proposal.qubit_id] = RetuneProposal(
            qubit_id=proposal.qubit_id,
            original_freq_ghz=original,
            proposed_freq_ghz=proposal.proposed_freq_ghz,
            reason="net retune from greedy collision-reduction search",
        )

    return ChipOptimizeResult(
        lattice_name=lattice.name,
        before=before,
        after=after,
        proposals=list(net_by_qubit.values()),
        iterations=iterations,
        converged=converged,
        assumptions=[
            f"Greedy coordinate descent on total detuning shortfall (MHz), not a "
            f"binary violation count: each step nudges the node with the largest "
            f"attributed shortfall by {step_mhz} MHz, kept only if it strictly "
            "reduces total shortfall.",
            f"Retuning bounded to +/-{max_retune_mhz} MHz from each qubit's original "
            "target (a fabrication-achievable-range constraint, not free tuning).",
            "This is a local search, not a proof of global optimality: a lattice "
            "may remain non-collision-free even after convergence of this search.",
            "Readout/coupler frequencies are not retuned by this optimizer.",
        ],
    )
