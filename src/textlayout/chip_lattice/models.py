"""Schemas for multi-qubit chip-level frequency-collision analysis.

Why this exists: a single-device closed loop (one IDC, one resonator, one
SQUID) cannot answer the question that actually determines whether a
multi-qubit processor works: do frequencies collide once process variation
(see :mod:`textlayout.yield_model`) is propagated across every qubit,
coupler, and readout resonator on the chip *simultaneously*? This module
makes the chip-level lattice, its frequency-collision rules, and the
resulting yield an explicit, testable, first-class object — not an
afterthought bolted onto single-device generation.

All numbers carry units. All Monte Carlo results carry a seed and are
reproducible.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

CHIP_LATTICE_SCHEMA = "textlayout.chip-lattice.v1"
COLLISION_REPORT_SCHEMA = "textlayout.chip-collision-report.v1"


class QubitNode(BaseModel):
    """One qubit/coupler/resonator mode in the lattice."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    qubit_id: str
    target_freq_ghz: float = Field(gt=0, description="Design target frequency (GHz).")
    readout_freq_ghz: float | None = Field(
        default=None, gt=0, description="Dedicated readout resonator frequency (GHz)."
    )
    anharmonicity_mhz: float = Field(
        default=-200.0, description="Qubit anharmonicity α (MHz); negative for transmons."
    )
    freq_sigma_mhz: float = Field(
        gt=0, description="1-sigma frequency spread from process variation (MHz)."
    )


class CouplerEdge(BaseModel):
    """A coupling element (direct or tunable) between two nodes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_a: str
    node_b: str
    coupler_freq_ghz: float | None = Field(
        default=None, gt=0, description="Tunable coupler mode frequency, if present (GHz)."
    )
    coupling_mhz: float = Field(gt=0, description="Static/nominal coupling strength g (MHz).")


class CollisionRules(BaseModel):
    """Forbidden-detuning windows, in MHz, following standard transmon collision taxonomy.

    Defaults are illustrative order-of-magnitude values from the published
    frequency-crowding / crosstalk literature for fixed-frequency transmon
    processors — NOT calibrated to any specific device or foundry process.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    qubit_qubit_min_detuning_mhz: float = Field(
        default=30.0, gt=0, description="Type-I: nearest-neighbor qubit-qubit min |Δf|."
    )
    qubit_readout_min_detuning_mhz: float = Field(
        default=500.0, gt=0, description="Qubit must be far from its own readout resonator."
    )
    qubit_coupler_min_detuning_mhz: float = Field(
        default=300.0, gt=0, description="Qubit must be far from its coupler mode."
    )
    two_photon_min_detuning_mhz: float = Field(
        default=30.0,
        gt=0,
        description="Type-II-like: |Δf - α| min separation (two-photon/higher-order hook).",
    )
    charge_parity_min_detuning_mhz: float = Field(
        default=30.0,
        gt=0,
        description="|2Δf - α| min separation (ZZ / next-order collision hook).",
    )


class QubitLattice(BaseModel):
    """A full chip: nodes, coupling graph, and the rules that must hold."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=CHIP_LATTICE_SCHEMA)
    name: str
    nodes: list[QubitNode]
    edges: list[CouplerEdge]
    rules: CollisionRules = Field(default_factory=CollisionRules)

    @model_validator(mode="after")
    def _edges_reference_known_nodes(self) -> QubitLattice:
        ids = {node.qubit_id for node in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("duplicate qubit_id in lattice nodes")
        for edge in self.edges:
            if edge.node_a not in ids or edge.node_b not in ids:
                raise ValueError(f"edge ({edge.node_a}, {edge.node_b}) references an unknown node")
            if edge.node_a == edge.node_b:
                raise ValueError(f"self-loop edge on node {edge.node_a!r}")
        return self

    def node(self, qubit_id: str) -> QubitNode:
        for node in self.nodes:
            if node.qubit_id == qubit_id:
                return node
        raise KeyError(f"qubit_id {qubit_id!r} not in lattice {self.name!r}")

    def neighbors(self, qubit_id: str) -> list[str]:
        result = []
        for edge in self.edges:
            if edge.node_a == qubit_id:
                result.append(edge.node_b)
            elif edge.node_b == qubit_id:
                result.append(edge.node_a)
        return result


class CollisionFinding(BaseModel):
    """One detected (or checked) collision between two nodes/channels."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule: str = Field(
        description="qubit_qubit | qubit_readout | qubit_coupler | two_photon | charge_parity"
    )
    node_a: str
    node_b: str
    detuning_mhz: float
    min_required_mhz: float
    violated: bool


class ChipCollisionReport(BaseModel):
    """Deterministic (nominal-frequency) collision check result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=COLLISION_REPORT_SCHEMA)
    lattice_name: str
    n_nodes: int
    findings: list[CollisionFinding]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def n_violations(self) -> int:
        return sum(1 for f in self.findings if f.violated)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def collision_free(self) -> bool:
        return self.n_violations == 0

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class RiskyPair(BaseModel):
    """One node pair ranked by Monte Carlo collision probability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_a: str
    node_b: str
    rule: str
    collision_probability: float = Field(ge=0, le=1)


class ChipYieldResult(BaseModel):
    """Monte Carlo collision-free chip yield across process variation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="textlayout.chip-yield.v1")
    lattice_name: str
    n_samples: int
    seed: int
    collision_free_pct: float = Field(ge=0, le=100)
    collision_free_ci95_pct: tuple[float, float]
    risky_pairs: list[RiskyPair]
    nominal_report: ChipCollisionReport
    assumptions: list[str] = Field(default_factory=list)
    provenance: dict[str, str] = Field(default_factory=dict)
    synthetic: bool = Field(default=True)

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class RetuneProposal(BaseModel):
    """One proposed target-frequency change to reduce collision probability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    qubit_id: str
    original_freq_ghz: float
    proposed_freq_ghz: float
    reason: str


class ChipOptimizeResult(BaseModel):
    """Result of the greedy target-frequency retuning optimizer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="textlayout.chip-optimize.v1")
    lattice_name: str
    before: ChipCollisionReport
    after: ChipCollisionReport
    proposals: list[RetuneProposal]
    iterations: int
    converged: bool
    assumptions: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")
