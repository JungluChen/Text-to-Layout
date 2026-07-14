"""Global one-to-one assignment of Palace modes between solved states."""

from __future__ import annotations

import math

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator


class AssignmentModeSignature(BaseModel):
    """Solver-independent observables used to preserve a modal identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode_index: int = Field(ge=1)
    frequency_ghz: float = Field(gt=0.0)
    regional_signature: dict[str, float] = Field(default_factory=dict)
    resonator_localization: float = Field(ge=0.0, le=1.0)
    physical_class: str


class PairMac(BaseModel):
    """Reference-mesh electric and magnetic MAC for one candidate edge."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    from_mode: int = Field(ge=1)
    to_mode: int = Field(ge=1)
    electric_mac: float = Field(ge=0.0, le=1.0)
    magnetic_mac: float = Field(ge=0.0, le=1.0)


class AssignmentWeights(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    frequency: float = Field(default=1.0, ge=0.0)
    electric_mac: float = Field(default=2.0, ge=0.0)
    magnetic_mac: float = Field(default=2.0, ge=0.0)
    signature: float = Field(default=1.0, ge=0.0)
    localization: float = Field(default=1.0, ge=0.0)
    physical_class: float = Field(default=1.0, ge=0.0)

    @model_validator(mode="after")
    def _nonzero(self) -> AssignmentWeights:
        if sum(self.model_dump().values()) <= 0.0:
            raise ValueError("at least one assignment weight must be positive")
        return self


class AssignedModePair(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    from_mode: int
    to_mode: int
    cost: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    global_alternative_margin: float = Field(ge=0.0)
    nearest_competitor_mode: int | None
    nearest_competitor_cost: float | None = Field(default=None, ge=0.0, le=1.0)
    components: dict[str, float]
    ambiguous: bool


class GlobalModeAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "textlayout.palace-global-mode-assignment.v1"
    status: str
    promotion_allowed: bool
    total_cost: float = Field(ge=0.0)
    pairs: list[AssignedModePair]
    unassigned_from_modes: list[int]
    unassigned_to_modes: list[int]


def _cosine_distance(left: dict[str, float], right: dict[str, float]) -> float:
    keys = sorted(set(left) | set(right))
    if not keys:
        return 1.0
    a = np.asarray([left.get(key, 0.0) for key in keys], dtype=float)
    b = np.asarray([right.get(key, 0.0) for key in keys], dtype=float)
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        raise ValueError("mode signatures must contain only finite values")
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator == 0.0:
        return 1.0
    similarity = float(np.dot(a, b) / denominator)
    return 1.0 - max(0.0, min(1.0, similarity))


def _pair_cost(
    left: AssignmentModeSignature,
    right: AssignmentModeSignature,
    mac: PairMac,
    weights: AssignmentWeights,
    frequency_scale_fraction: float,
) -> tuple[float, dict[str, float]]:
    frequency = min(
        1.0,
        abs(right.frequency_ghz - left.frequency_ghz)
        / (left.frequency_ghz * frequency_scale_fraction),
    )
    components = {
        "frequency_cost": frequency,
        "electric_mac_cost": 1.0 - mac.electric_mac,
        "magnetic_mac_cost": 1.0 - mac.magnetic_mac,
        "signature_cost": _cosine_distance(
            left.regional_signature, right.regional_signature
        ),
        "localization_cost": abs(
            left.resonator_localization - right.resonator_localization
        ),
        "class_mismatch_cost": float(left.physical_class != right.physical_class),
    }
    weighted = (
        weights.frequency * components["frequency_cost"]
        + weights.electric_mac * components["electric_mac_cost"]
        + weights.magnetic_mac * components["magnetic_mac_cost"]
        + weights.signature * components["signature_cost"]
        + weights.localization * components["localization_cost"]
        + weights.physical_class * components["class_mismatch_cost"]
    )
    return weighted / sum(weights.model_dump().values()), components


def assign_modes_globally(
    previous: list[AssignmentModeSignature],
    current: list[AssignmentModeSignature],
    pair_macs: list[PairMac],
    *,
    weights: AssignmentWeights | None = None,
    frequency_scale_fraction: float = 0.1,
    minimum_confidence: float = 0.8,
    minimum_global_margin: float = 0.02,
) -> GlobalModeAssignment:
    """Solve a Hungarian assignment and reject globally ambiguous identities."""
    if not previous or not current:
        raise ValueError("both solved states must contain at least one mode")
    if frequency_scale_fraction <= 0.0:
        raise ValueError("frequency_scale_fraction must be positive")
    if not 0.0 <= minimum_confidence <= 1.0 or minimum_global_margin < 0.0:
        raise ValueError("invalid assignment acceptance thresholds")
    if len({mode.mode_index for mode in previous}) != len(previous):
        raise ValueError("previous mode indices must be unique")
    if len({mode.mode_index for mode in current}) != len(current):
        raise ValueError("current mode indices must be unique")
    mac_by_edge = {(item.from_mode, item.to_mode): item for item in pair_macs}
    expected = {
        (left.mode_index, right.mode_index) for left in previous for right in current
    }
    if set(mac_by_edge) != expected:
        missing = sorted(expected - set(mac_by_edge))
        extra = sorted(set(mac_by_edge) - expected)
        raise ValueError(f"pair MAC matrix must be complete; missing={missing}, extra={extra}")

    from scipy.optimize import linear_sum_assignment  # type: ignore[import-untyped]

    rules = weights or AssignmentWeights()
    matrix = np.empty((len(previous), len(current)), dtype=float)
    components: dict[tuple[int, int], dict[str, float]] = {}
    for row, left in enumerate(previous):
        for column, right in enumerate(current):
            edge = (left.mode_index, right.mode_index)
            matrix[row, column], components[edge] = _pair_cost(
                left,
                right,
                mac_by_edge[edge],
                rules,
                frequency_scale_fraction,
            )
    rows, columns = linear_sum_assignment(matrix)
    optimum = float(matrix[rows, columns].sum())
    selected = list(zip(rows.tolist(), columns.tolist()))
    pairs: list[AssignedModePair] = []
    for row, column in selected:
        forbidden = matrix.copy()
        forbidden[row, column] = math.inf
        try:
            alt_rows, alt_columns = linear_sum_assignment(forbidden)
            alternative = float(forbidden[alt_rows, alt_columns].sum())
            margin = max(0.0, alternative - optimum)
        except ValueError:
            margin = 1.0
        alternatives = [
            (float(matrix[row, candidate]), candidate)
            for candidate in range(matrix.shape[1])
            if candidate != column
        ]
        alternatives.sort(key=lambda item: (item[0], current[item[1]].mode_index))
        competitor_cost, competitor_column = alternatives[0] if alternatives else (None, None)
        cost = float(matrix[row, column])
        confidence = 1.0 - cost
        ambiguous = confidence < minimum_confidence or margin < minimum_global_margin
        edge = (previous[row].mode_index, current[column].mode_index)
        pairs.append(
            AssignedModePair(
                from_mode=edge[0],
                to_mode=edge[1],
                cost=cost,
                confidence=confidence,
                global_alternative_margin=margin,
                nearest_competitor_mode=(
                    current[competitor_column].mode_index
                    if competitor_column is not None
                    else None
                ),
                nearest_competitor_cost=competitor_cost,
                components=components[edge],
                ambiguous=ambiguous,
            )
        )
    assigned_from = {previous[row].mode_index for row, _ in selected}
    assigned_to = {current[column].mode_index for _, column in selected}
    ambiguous = any(pair.ambiguous for pair in pairs)
    return GlobalModeAssignment(
        status="MODE_TRACKING_AMBIGUOUS" if ambiguous else "MODE_TRACKING_ASSIGNED",
        promotion_allowed=not ambiguous,
        total_cost=optimum,
        pairs=sorted(pairs, key=lambda pair: pair.from_mode),
        unassigned_from_modes=sorted(
            mode.mode_index for mode in previous if mode.mode_index not in assigned_from
        ),
        unassigned_to_modes=sorted(
            mode.mode_index for mode in current if mode.mode_index not in assigned_to
        ),
    )
