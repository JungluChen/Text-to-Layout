"""Deterministic frequency-collision rule evaluation for a qubit lattice.

Collision taxonomy (standard fixed-frequency transmon literature; see
docs/chip_collision_yield.md for the per-rule reference):

- ``qubit_qubit``: nearest-neighbor |Δf| too small (direct hybridization risk).
- ``qubit_readout``: a qubit too close to its own readout resonator.
- ``qubit_coupler``: a qubit too close to its (tunable) coupler mode.
- ``two_photon``: |Δf − |α|| too small — a two-photon exchange resonance hook.
- ``charge_parity``: |2Δf − |α|| too small — a next-order resonance hook.

All checks are pure functions of a frequency assignment; the Monte Carlo
module reuses this same evaluator per sampled draw so the nominal report and
the statistical yield are guaranteed consistent with each other.
"""

from __future__ import annotations

from textlayout.chip_lattice.models import (
    ChipCollisionReport,
    CollisionFinding,
    QubitLattice,
)

#: Frequencies are stored as GHz floats; a detuning near a rule's MHz threshold
#: can land on either side of it purely from binary floating-point
#: representation (e.g. 5.010-4.980 != exactly 0.030 in double precision).
#: 1 Hz (1e-6 MHz) is far below any physically meaningful detuning distinction
#: and absorbs that noise without changing which real-world cases pass.
_EPS_MHZ = 1e-6


def _finding(
    rule: str, node_a: str, node_b: str, detuning_mhz: float, min_required_mhz: float
) -> CollisionFinding:
    return CollisionFinding(
        rule=rule,
        node_a=node_a,
        node_b=node_b,
        detuning_mhz=detuning_mhz,
        min_required_mhz=min_required_mhz,
        violated=detuning_mhz < min_required_mhz - _EPS_MHZ,
    )


def evaluate_collisions(
    lattice: QubitLattice, frequencies_ghz: dict[str, float]
) -> list[CollisionFinding]:
    """Evaluate every collision rule for one frequency assignment.

    ``frequencies_ghz`` maps qubit_id -> the frequency to use for THIS
    evaluation (nominal target, or one Monte Carlo draw). Readout and coupler
    frequencies are taken from the lattice definition itself (not perturbed) —
    see the module docs for that simplification.
    """
    rules = lattice.rules
    findings: list[CollisionFinding] = []

    for edge in lattice.edges:
        fa = frequencies_ghz[edge.node_a]
        fb = frequencies_ghz[edge.node_b]
        detuning_mhz = abs(fa - fb) * 1e3
        findings.append(
            _finding(
                "qubit_qubit", edge.node_a, edge.node_b, detuning_mhz,
                rules.qubit_qubit_min_detuning_mhz,
            )
        )

        node_a = lattice.node(edge.node_a)
        node_b = lattice.node(edge.node_b)
        alpha_mhz = (abs(node_a.anharmonicity_mhz) + abs(node_b.anharmonicity_mhz)) / 2.0
        findings.append(
            _finding(
                "two_photon", edge.node_a, edge.node_b,
                abs(detuning_mhz - alpha_mhz), rules.two_photon_min_detuning_mhz,
            )
        )
        findings.append(
            _finding(
                "charge_parity", edge.node_a, edge.node_b,
                abs(2.0 * detuning_mhz - alpha_mhz), rules.charge_parity_min_detuning_mhz,
            )
        )

        if edge.coupler_freq_ghz is not None:
            for node_id, freq in ((edge.node_a, fa), (edge.node_b, fb)):
                detuning = abs(freq - edge.coupler_freq_ghz) * 1e3
                findings.append(
                    _finding(
                        "qubit_coupler", node_id, f"coupler({edge.node_a},{edge.node_b})",
                        detuning, rules.qubit_coupler_min_detuning_mhz,
                    )
                )

    for node in lattice.nodes:
        if node.readout_freq_ghz is None:
            continue
        freq = frequencies_ghz[node.qubit_id]
        detuning_mhz = abs(freq - node.readout_freq_ghz) * 1e3
        findings.append(
            _finding(
                "qubit_readout", node.qubit_id, f"readout({node.qubit_id})",
                detuning_mhz, rules.qubit_readout_min_detuning_mhz,
            )
        )

    return findings


def analyze_nominal(lattice: QubitLattice) -> ChipCollisionReport:
    """Deterministic collision check at each node's nominal target frequency."""
    frequencies = {node.qubit_id: node.target_freq_ghz for node in lattice.nodes}
    findings = evaluate_collisions(lattice, frequencies)
    return ChipCollisionReport(
        lattice_name=lattice.name, n_nodes=len(lattice.nodes), findings=findings
    )
