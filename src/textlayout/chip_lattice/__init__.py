"""Multi-qubit chip-level frequency-collision analysis and yield.

Why this exists: single-device closed loops (one IDC, one SQUID) cannot
answer whether a *processor* works. This package extends the design loop from
one device to a lattice of qubits/couplers/readout resonators, checking the
standard collision taxonomy (qubit-qubit, qubit-readout, qubit-coupler,
two-photon, charge-parity) both deterministically at nominal frequencies and
statistically via seeded Monte Carlo propagation of per-node frequency
uncertainty (typically produced upstream by :mod:`textlayout.yield_model`).

See :mod:`textlayout.chip_lattice.collision` for the rule definitions,
:mod:`textlayout.chip_lattice.monte_carlo` for the yield propagation, and
:mod:`textlayout.chip_lattice.optimizer` for the greedy frequency-allocation
retuning search.
"""

from textlayout.chip_lattice.collision import analyze_nominal, evaluate_collisions
from textlayout.chip_lattice.models import (
    CHIP_LATTICE_SCHEMA,
    COLLISION_REPORT_SCHEMA,
    ChipCollisionReport,
    ChipOptimizeResult,
    ChipYieldResult,
    CollisionFinding,
    CollisionRules,
    CouplerEdge,
    QubitLattice,
    QubitNode,
    RetuneProposal,
    RiskyPair,
)
from textlayout.chip_lattice.monte_carlo import run_chip_collision_yield
from textlayout.chip_lattice.optimizer import optimize_frequencies
from textlayout.chip_lattice.report import (
    render_markdown,
    render_optimize_markdown,
    write_chip_optimize_report,
    write_chip_yield_report,
)

__all__ = [
    "CHIP_LATTICE_SCHEMA",
    "COLLISION_REPORT_SCHEMA",
    "ChipCollisionReport",
    "ChipOptimizeResult",
    "ChipYieldResult",
    "CollisionFinding",
    "CollisionRules",
    "CouplerEdge",
    "QubitLattice",
    "QubitNode",
    "RetuneProposal",
    "RiskyPair",
    "analyze_nominal",
    "evaluate_collisions",
    "optimize_frequencies",
    "render_markdown",
    "render_optimize_markdown",
    "run_chip_collision_yield",
    "write_chip_optimize_report",
    "write_chip_yield_report",
]
