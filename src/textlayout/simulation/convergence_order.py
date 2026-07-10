"""Observed order of convergence, Richardson extrapolation, and the GCI.

Comparing the two finest levels answers "did the number stop moving?". It cannot
answer "is it moving the way a convergent discretisation moves?", and the two
come apart in the case that matters: an *oscillatory* sequence can place its two
finest values arbitrarily close together while the underlying error is not
decreasing at all. A two-point test reads that as converged.

Three levels expose the difference. With grid ratios r and value differences
eps, the sign of ``eps32/eps21`` separates monotonic from oscillatory behaviour,
its magnitude yields the *observed order* p, and p yields both a Richardson
estimate of the mesh-independent value and Roache's Grid Convergence Index -- an
error band with a declared safety factor rather than an eyeballed tolerance.

Definitions follow Roache (1994, 1997) and the ASME V&V-20 procedure:

    r21 = h2/h1,  r32 = h3/h2                 (h1 finest)
    eps21 = f2 - f1,  eps32 = f3 - f2
    s = sign(eps32 / eps21)
    p = |ln|eps32/eps21| + q(p)| / ln(r21),  q(p) = ln((r21^p - s)/(r32^p - s))
    f_extrapolated = f1 + (f1 - f2) / (r21^p - 1)
    GCI21 = Fs * |(f1 - f2)/f1| / (r21^p - 1)

``q(p)`` vanishes when the refinement ratio is constant; it is solved by fixed
point iteration otherwise, which is why non-uniform refinement is supported
rather than silently assumed away.

**Three levels cannot self-certify.** ``p`` is *fitted* to the three finest
points, so any check of the form "does the error decay at rate p?" evaluated on
those same three points is a tautology -- with uniform refinement it returns 1.0
identically, and with the relative-error GCI it returns f1/f2, which is ~1.0 for
any sequence whatsoever. Establishing that the levels lie in the asymptotic range
requires independent information, and this module accepts exactly two kinds:

- a **fourth level**, so ``p`` can be refitted on the next-coarser triple and the
  two estimates compared; or
- a declared **formal order** of the discretisation, against which the observed
  ``p`` is checked.

Given neither, ``in_asymptotic_range`` is ``False`` and the study is not
converged. That is a strict stance, and it is the correct one: a three-level
study with an unknown scheme order has measured a number, not bounded its error.

Richardson extrapolation presumes a *monotone* sequence in the asymptotic range.
Where that presumption fails this module says so and withholds the extrapolated
value, instead of returning a number whose derivation does not hold.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

#: Roache's safety factor for a three-grid study. 1.25 is the value justified by
#: the reference set; 3.0 applies to two-grid studies, which this module refuses.
SAFETY_FACTOR_THREE_GRID = 1.25

#: Below this relative change the two levels are numerically identical and the
#: order of convergence is undefined rather than infinite.
_EXACT_RELATIVE_TOLERANCE = 1e-12

#: An observed order at or below this is not convergence in any useful sense.
_MIN_USEFUL_ORDER = 0.1

Behaviour = Literal["monotonic", "oscillatory", "exact", "indeterminate"]


@dataclass(frozen=True)
class GridLevel:
    """One solve, at one representative grid spacing."""

    characteristic_length: float
    value: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.characteristic_length) or self.characteristic_length <= 0:
            raise ValueError(
                f"characteristic_length must be finite and positive, "
                f"got {self.characteristic_length!r}"
            )
        if not math.isfinite(self.value):
            raise ValueError(f"value must be finite, got {self.value!r}")


@dataclass(frozen=True)
class ConvergenceOrder:
    """What three levels establish about a quantity, and what they do not."""

    behaviour: Behaviour
    observed_order: float | None = None
    extrapolated_value: float | None = None
    #: Roache GCI on the finest grid, as a percentage. This is the *declared*
    #: numerical uncertainty of `values[-1]`.
    gci_percent: float | None = None
    #: Evidence that ``observed_order`` is stable rather than an artefact of the
    #: three points it was fitted to: ``p_fine / p_coarse`` when a fourth level
    #: exists, else ``p / expected_order`` when a formal order was declared.
    #: ``None`` when neither is available -- in which case nothing is claimed.
    asymptotic_ratio: float | None = None
    in_asymptotic_range: bool = False
    richardson_applicable: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def converged(self) -> bool:
        """Never true for an oscillatory or indeterminate sequence.

        A converged claim requires a positive observed order in the asymptotic
        range, or exact agreement. Closeness of the two finest values is not
        sufficient and is deliberately not consulted here.
        """
        if self.behaviour == "exact":
            return True
        return (
            self.behaviour == "monotonic"
            and self.in_asymptotic_range
            and self.observed_order is not None
            and self.observed_order > _MIN_USEFUL_ORDER
        )


def _solve_order(
    ratio_21: float, ratio_32: float, epsilon_21: float, epsilon_32: float, sign: float
) -> float | None:
    """Fixed-point solve of the Roache order equation. ``None`` if it will not settle."""
    magnitude = abs(epsilon_32 / epsilon_21)
    order = 1.0
    for _ in range(200):
        q = math.log((ratio_21**order - sign) / (ratio_32**order - sign))
        updated = abs(math.log(magnitude) + q) / math.log(ratio_21)
        if not math.isfinite(updated):
            return None
        if abs(updated - order) < 1e-12:
            return updated
        order = updated
    return None  # did not converge: the levels do not describe a single power law


def _assess_asymptotic_range(
    levels: list[GridLevel],
    order: float,
    *,
    expected_order: float | None,
    order_tolerance: float,
    notes: list[str],
) -> tuple[float | None, bool]:
    """Is ``order`` a property of the discretisation, or of these three points?

    Answered only from information the three finest points do not already
    contain: a refit on the next-coarser triple, or a declared formal order.
    """
    if len(levels) >= 4:
        coarser = _order_only(levels[:-1])
        if coarser is None:
            notes.append(
                "the next-coarser triple yields no usable order, so p cannot be shown stable"
            )
            return None, False
        ratio = order / coarser
        stable = abs(order - coarser) <= order_tolerance
        if not stable:
            notes.append(
                f"observed order moves from {coarser:.4f} to {order:.4f} between successive "
                f"triples (tolerance {order_tolerance}); the levels are not yet in the "
                "asymptotic range"
            )
        return ratio, stable

    if expected_order is not None:
        declared_ratio = order / expected_order if expected_order else None
        stable = abs(order - expected_order) <= order_tolerance
        if not stable:
            notes.append(
                f"observed order {order:.4f} differs from the declared formal order "
                f"{expected_order} by more than {order_tolerance}; the levels are not in "
                "the asymptotic range of that scheme"
            )
        return declared_ratio, stable

    notes.append(
        "three levels and no declared formal order: the asymptotic range cannot be "
        "established, because p was fitted to these very points. Supply a fourth level "
        "or an expected_order."
    )
    return None, False


def _order_only(levels: list[GridLevel]) -> float | None:
    """Refit ``p`` on a triple, returning ``None`` when it is not usable."""
    coarse, medium, fine = levels[-3], levels[-2], levels[-1]
    epsilon_21 = medium.value - fine.value
    epsilon_32 = coarse.value - medium.value
    if epsilon_21 == 0 or epsilon_32 == 0:
        return None
    sign = math.copysign(1.0, epsilon_32 / epsilon_21)
    order = _solve_order(
        medium.characteristic_length / fine.characteristic_length,
        coarse.characteristic_length / medium.characteristic_length,
        epsilon_21,
        epsilon_32,
        sign,
    )
    if order is None or not math.isfinite(order) or order <= _MIN_USEFUL_ORDER:
        return None
    return order


def estimate_order(
    levels: list[GridLevel],
    *,
    expected_order: float | None = None,
    order_tolerance: float = 0.5,
    safety_factor: float = SAFETY_FACTOR_THREE_GRID,
) -> ConvergenceOrder:
    """Assess a quantity over >= 3 levels, finest last.

    ``p`` and the GCI are computed from the three finest levels -- that is what
    the GCI is defined over. Whether those levels lie in the asymptotic range is
    established from *independent* information: a fourth level, or a declared
    ``expected_order`` for the discretisation. See the module docstring for why a
    three-point self-check cannot do it.

    Every level must be a genuine refinement, so a repeated or coarsening grid is
    rejected rather than quietly dropped.
    """
    if len(levels) < 3:
        raise ValueError(
            f"an order estimate needs at least 3 refinement levels, got {len(levels)}; "
            "two levels cannot distinguish monotonic from oscillatory convergence"
        )
    lengths = [level.characteristic_length for level in levels]
    if any(a <= b for a, b in zip(lengths, lengths[1:])):
        raise ValueError(f"levels must be strictly refined (coarse to fine), got {lengths}")
    if safety_factor <= 0:
        raise ValueError(f"safety_factor must be positive, got {safety_factor!r}")

    coarse, medium, fine = levels[-3], levels[-2], levels[-1]
    h1, h2, h3 = fine.characteristic_length, medium.characteristic_length, coarse.characteristic_length
    f1, f2, f3 = fine.value, medium.value, coarse.value
    ratio_21, ratio_32 = h2 / h1, h3 / h2

    epsilon_21, epsilon_32 = f2 - f1, f3 - f2
    scale = abs(f1) if f1 != 0 else 1.0

    if abs(epsilon_21) <= _EXACT_RELATIVE_TOLERANCE * scale:
        return ConvergenceOrder(
            behaviour="exact",
            extrapolated_value=f1,
            gci_percent=0.0,
            in_asymptotic_range=True,
            richardson_applicable=False,
            notes=["the two finest levels agree to machine precision; order is undefined"],
        )
    if abs(epsilon_32) <= _EXACT_RELATIVE_TOLERANCE * scale:
        return ConvergenceOrder(
            behaviour="indeterminate",
            notes=[
                "the two coarsest levels agree but the two finest do not; "
                "the sequence is not described by a single power law"
            ],
        )

    sign = math.copysign(1.0, epsilon_32 / epsilon_21)
    behaviour: Behaviour = "monotonic" if sign > 0 else "oscillatory"
    notes: list[str] = []
    if behaviour == "oscillatory":
        notes.append(
            "eps32/eps21 < 0: the sequence oscillates. The two finest values may lie "
            "arbitrarily close together without the error decreasing, so their proximity "
            "is not evidence of convergence."
        )

    order = _solve_order(ratio_21, ratio_32, epsilon_21, epsilon_32, sign)
    if order is None or not math.isfinite(order) or order <= _MIN_USEFUL_ORDER:
        notes.append(
            f"no usable observed order (p={order!r}); the levels do not follow a single "
            "power law, so neither Richardson extrapolation nor a GCI is defined"
        )
        return ConvergenceOrder(behaviour="indeterminate", observed_order=order, notes=notes)

    denominator_21 = ratio_21**order - 1.0
    denominator_32 = ratio_32**order - 1.0
    if denominator_21 <= 0 or denominator_32 <= 0:
        notes.append("r^p - 1 is non-positive; the GCI is undefined")
        return ConvergenceOrder(behaviour="indeterminate", observed_order=order, notes=notes)

    relative_error_21 = abs(epsilon_21 / f1) if f1 != 0 else abs(epsilon_21)
    gci_21 = safety_factor * relative_error_21 / denominator_21

    asymptotic_ratio, in_asymptotic_range = _assess_asymptotic_range(
        levels, order, expected_order=expected_order, order_tolerance=order_tolerance, notes=notes
    )

    richardson_applicable = behaviour == "monotonic" and in_asymptotic_range
    extrapolated = f1 + (f1 - f2) / denominator_21 if richardson_applicable else None
    if not richardson_applicable:
        notes.append(
            "Richardson extrapolation withheld: it presumes a monotone sequence in the "
            "asymptotic range, and that presumption does not hold here"
        )

    return ConvergenceOrder(
        behaviour=behaviour,
        observed_order=order,
        extrapolated_value=extrapolated,
        gci_percent=gci_21 * 100.0,
        asymptotic_ratio=asymptotic_ratio,
        in_asymptotic_range=in_asymptotic_range,
        richardson_applicable=richardson_applicable,
        notes=notes,
    )


@dataclass(frozen=True)
class CategoryResult:
    """One convergence category (frequency, field energy, domain size, ...)."""

    name: str
    order: ConvergenceOrder
    mandatory: bool = True

    @property
    def passed(self) -> bool:
        return self.order.converged


@dataclass(frozen=True)
class ConvergenceVerdict:
    """Whether *every* mandatory category converged. Never an average."""

    categories: list[CategoryResult]

    @property
    def mandatory(self) -> list[CategoryResult]:
        return [category for category in self.categories if category.mandatory]

    @property
    def failures(self) -> list[str]:
        return [category.name for category in self.mandatory if not category.passed]

    @property
    def passed(self) -> bool:
        """A single unconverged mandatory category sinks the study.

        Averaging would let a well-resolved frequency mask an unconverged domain
        size, which is precisely how a resonance converges beautifully onto the
        wrong answer inside a box that is still too small.
        """
        return bool(self.mandatory) and not self.failures

    @property
    def worst_gci_percent(self) -> float | None:
        """The largest declared uncertainty across mandatory categories."""
        values = [
            category.order.gci_percent
            for category in self.mandatory
            if category.order.gci_percent is not None
        ]
        return max(values) if values else None


def evaluate_categories(categories: list[CategoryResult]) -> ConvergenceVerdict:
    if not categories:
        raise ValueError("a convergence verdict needs at least one category")
    if not any(category.mandatory for category in categories):
        raise ValueError("at least one convergence category must be mandatory")
    return ConvergenceVerdict(categories=list(categories))
