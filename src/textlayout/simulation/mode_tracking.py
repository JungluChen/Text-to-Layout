"""Follow one physical eigenmode across mesh refinements.

Mode index N is not a physical identity. Refine the mesh and two nearby modes
can swap order; add a mode to the search window and every index shifts. A
convergence study that reads ``frequencies[2]`` at each level is therefore
comparing *different modes* the moment they cross, and will report either a
spurious jump (looks like divergence) or a spurious agreement (looks like
convergence onto the wrong resonance).

Identity is carried by the field, not the index. This module scores candidate
modes against a reference using, where available:

- **frequency proximity** -- necessary, never sufficient; it is exactly what
  fails at a crossing.
- **electric- and magnetic-field overlap** -- cosine similarity of the energy
  fraction per named physical region.
- **energy localization** -- whether the dominant region is the same one.
- **port participation** -- cosine similarity of per-port coupling.

A match is accepted only when it is **mutually best** and clears a **margin**
over the runner-up. Two degenerate modes produce near-equal scores, so no margin
is cleared and the match is *rejected* rather than guessed. An ambiguous mode is
not a tracking failure to be papered over -- it is a result that must not be
promoted to a converged frequency.

Nothing here imports a solver: the algorithm is exercised on constructed
signatures, never on a fabricated Palace run.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

from textlayout.evidence.canonical import SanityCheck


@dataclass(frozen=True)
class ModeSignature:
    """What one eigenmode looks like, beyond its position in a list."""

    index: int
    frequency_ghz: float
    #: Fraction of electric field energy in each named physical region.
    electric_energy_by_region: Mapping[str, float] = field(default_factory=dict)
    magnetic_energy_by_region: Mapping[str, float] = field(default_factory=dict)
    #: Coupling to each named port.
    port_participation: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not math.isfinite(self.frequency_ghz) or self.frequency_ghz <= 0:
            raise ValueError(
                f"mode {self.index} has a non-physical frequency: {self.frequency_ghz!r}"
            )


@dataclass(frozen=True)
class MatchCriteria:
    """How much each observable is trusted, and how sure a match must be.

    ``frequency_window_fraction`` is the relative frequency change beyond which
    proximity contributes nothing. It is deliberately *not* a veto: at a true
    crossing the field overlap must be allowed to outvote frequency.
    """

    frequency_weight: float = 1.0
    electric_overlap_weight: float = 2.0
    magnetic_overlap_weight: float = 1.0
    localization_weight: float = 1.0
    port_weight: float = 1.0

    frequency_window_fraction: float = 0.10
    #: A match must score at least this well in absolute terms.
    min_score: float = 0.5
    #: ...and beat the runner-up by at least this much, or it is ambiguous.
    margin: float = 0.10

    def __post_init__(self) -> None:
        if self.frequency_window_fraction <= 0:
            raise ValueError("frequency_window_fraction must be positive")
        if not 0.0 <= self.min_score <= 1.0:
            raise ValueError("min_score must lie in [0, 1]")
        if self.margin < 0:
            raise ValueError("margin must not be negative")


@dataclass(frozen=True)
class ModeMatch:
    """One accepted correspondence, with the evidence that it is unambiguous."""

    reference_index: int
    matched_index: int
    score: float
    runner_up_score: float
    components: Mapping[str, float]

    @property
    def margin(self) -> float:
        return self.score - self.runner_up_score


class AmbiguousModeMatch(ValueError):
    """The best candidate could not be distinguished from the runner-up."""


def _cosine(left: Mapping[str, float], right: Mapping[str, float]) -> float | None:
    """Cosine similarity over the union of region names; ``None`` if unusable."""
    keys = set(left) | set(right)
    if not keys:
        return None
    a = [float(left.get(key, 0.0)) for key in sorted(keys)]
    b = [float(right.get(key, 0.0)) for key in sorted(keys)]
    if any(not math.isfinite(value) for value in (*a, *b)):
        return None
    norm_a = math.sqrt(sum(value * value for value in a))
    norm_b = math.sqrt(sum(value * value for value in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return None
    dot = sum(x * y for x, y in zip(a, b))
    # Clamp: floating point can push a self-comparison a hair above 1.0.
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


def _dominant(region_energy: Mapping[str, float]) -> str | None:
    if not region_energy:
        return None
    return max(region_energy, key=lambda key: region_energy[key])


def _frequency_proximity(reference: float, candidate: float, window: float) -> float:
    relative = abs(candidate - reference) / reference
    return max(0.0, 1.0 - relative / window)


def score_pair(
    reference: ModeSignature, candidate: ModeSignature, criteria: MatchCriteria
) -> tuple[float, dict[str, float]]:
    """Weighted mean of the observables that both modes actually carry.

    Weights are renormalised over the *available* components, so a solver that
    reports no port participation is not silently penalised -- it simply casts
    no vote on that axis.
    """
    components: dict[str, float] = {
        "frequency": _frequency_proximity(
            reference.frequency_ghz, candidate.frequency_ghz, criteria.frequency_window_fraction
        )
    }
    weights: dict[str, float] = {"frequency": criteria.frequency_weight}

    electric = _cosine(reference.electric_energy_by_region, candidate.electric_energy_by_region)
    if electric is not None:
        components["electric_overlap"] = electric
        weights["electric_overlap"] = criteria.electric_overlap_weight

    magnetic = _cosine(reference.magnetic_energy_by_region, candidate.magnetic_energy_by_region)
    if magnetic is not None:
        components["magnetic_overlap"] = magnetic
        weights["magnetic_overlap"] = criteria.magnetic_overlap_weight

    reference_peak = _dominant(reference.electric_energy_by_region)
    candidate_peak = _dominant(candidate.electric_energy_by_region)
    if reference_peak is not None and candidate_peak is not None:
        components["localization"] = 1.0 if reference_peak == candidate_peak else 0.0
        weights["localization"] = criteria.localization_weight

    ports = _cosine(reference.port_participation, candidate.port_participation)
    if ports is not None:
        components["port_participation"] = ports
        weights["port_participation"] = criteria.port_weight

    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise ValueError("every match criterion has zero weight; nothing can be compared")
    score = sum(components[name] * weights[name] for name in components) / total_weight
    return score, components


def _ranked(
    reference: ModeSignature, candidates: list[ModeSignature], criteria: MatchCriteria
) -> list[tuple[float, dict[str, float], ModeSignature]]:
    scored = [(*score_pair(reference, candidate, criteria), candidate) for candidate in candidates]
    return sorted(scored, key=lambda item: (-item[0], item[2].index))


def match_mode(
    reference: ModeSignature,
    candidates: list[ModeSignature],
    *,
    criteria: MatchCriteria | None = None,
) -> ModeMatch:
    """The candidate that *is* ``reference``, or raise rather than guess.

    Acceptance requires the best candidate to clear ``min_score``, to beat the
    runner-up by ``margin``, and to be **mutually** best -- the reverse match
    from that candidate back over the reference set must select ``reference``.
    Mutuality is what stops two references from both claiming one candidate at a
    near-degeneracy.
    """
    rules = criteria or MatchCriteria()
    if not candidates:
        raise AmbiguousModeMatch(f"mode {reference.index}: no candidate modes to match against")

    ranked = _ranked(reference, candidates, rules)
    best_score, components, best = ranked[0]
    runner_up = ranked[1][0] if len(ranked) > 1 else 0.0

    if best_score < rules.min_score:
        raise AmbiguousModeMatch(
            f"mode {reference.index} at {reference.frequency_ghz:.6g} GHz: best candidate "
            f"(mode {best.index}) scores {best_score:.4f} < min_score {rules.min_score}; "
            "the mode was not found in this level"
        )
    if best_score - runner_up < rules.margin:
        raise AmbiguousModeMatch(
            f"mode {reference.index} at {reference.frequency_ghz:.6g} GHz: candidates "
            f"{best.index} ({best_score:.4f}) and {ranked[1][2].index} ({runner_up:.4f}) are "
            f"indistinguishable within margin {rules.margin}; refusing to guess which mode "
            "this is -- a degenerate pair cannot be tracked by score alone"
        )
    return ModeMatch(
        reference_index=reference.index,
        matched_index=best.index,
        score=best_score,
        runner_up_score=runner_up,
        components=components,
    )


def _mutually_best(
    reference: ModeSignature,
    candidates: list[ModeSignature],
    references: list[ModeSignature],
    criteria: MatchCriteria,
) -> ModeMatch:
    forward = match_mode(reference, candidates, criteria=criteria)
    chosen = next(mode for mode in candidates if mode.index == forward.matched_index)
    backward = match_mode(chosen, references, criteria=criteria)
    if backward.matched_index != reference.index:
        raise AmbiguousModeMatch(
            f"mode {reference.index} claims candidate {chosen.index}, but candidate "
            f"{chosen.index} prefers reference {backward.matched_index}; the assignment is "
            "not mutual, so at least one of these modes is being mis-identified"
        )
    return forward


@dataclass(frozen=True)
class TrackedMode:
    """One physical mode followed through every refinement level."""

    indices: list[int]
    frequencies_ghz: list[float]
    matches: list[ModeMatch]

    @property
    def worst_margin(self) -> float:
        """The least confident hop in the chain. Reported, never averaged away."""
        return min((match.margin for match in self.matches), default=float("inf"))

    @property
    def crossed(self) -> bool:
        """True when the mode changed its position in the frequency ordering."""
        return len(set(self.indices)) > 1


def track_across_levels(
    levels: list[list[ModeSignature]],
    *,
    seed_index: int | None = None,
    seed_frequency_ghz: float | None = None,
    criteria: MatchCriteria | None = None,
) -> TrackedMode:
    """Follow one mode from the coarsest level to the finest.

    Seed by explicit index, or by nearest frequency to ``seed_frequency_ghz``.
    Each hop matches against the *previous level's* signature rather than the
    original seed, so a mode that drifts steadily is still followed while a mode
    that swaps identity is caught.
    """
    rules = criteria or MatchCriteria()
    if len(levels) < 2:
        raise ValueError("mode tracking needs at least two refinement levels")
    if any(not level for level in levels):
        raise ValueError("every refinement level must report at least one mode")
    if (seed_index is None) == (seed_frequency_ghz is None):
        raise ValueError("supply exactly one of seed_index or seed_frequency_ghz")

    if seed_index is not None:
        current = next((mode for mode in levels[0] if mode.index == seed_index), None)
        if current is None:
            raise ValueError(f"no mode with index {seed_index} in the coarsest level")
    else:
        assert seed_frequency_ghz is not None
        current = min(
            levels[0], key=lambda mode: abs(mode.frequency_ghz - seed_frequency_ghz)
        )

    indices = [current.index]
    frequencies = [current.frequency_ghz]
    matches: list[ModeMatch] = []

    for previous_level, next_level in zip(levels, levels[1:]):
        match = _mutually_best(current, next_level, previous_level, rules)
        current = next(mode for mode in next_level if mode.index == match.matched_index)
        indices.append(current.index)
        frequencies.append(current.frequency_ghz)
        matches.append(match)

    return TrackedMode(indices=indices, frequencies_ghz=frequencies, matches=matches)


def mode_tracking_check(
    levels: list[list[ModeSignature]],
    *,
    seed_index: int | None = None,
    seed_frequency_ghz: float | None = None,
    criteria: MatchCriteria | None = None,
) -> tuple[SanityCheck, TrackedMode | None]:
    """A ``SanityCheck`` a convergence study hands to the evidence ladder.

    An un-trackable mode is not an inconvenience to be worked around. If the
    frequencies at each level are not measurements of the same physical mode,
    their agreement means nothing and their disagreement means nothing. Passing
    this check into ``mesh_convergence_evidence`` makes such a study
    ``SIMULATION_INVALID`` -- the only honest outcome, and one the canonical
    schema already refuses to let carry an extracted value.
    """
    try:
        tracked = track_across_levels(
            levels,
            seed_index=seed_index,
            seed_frequency_ghz=seed_frequency_ghz,
            criteria=criteria,
        )
    except AmbiguousModeMatch as exc:
        return SanityCheck(name="modes_unambiguously_tracked", passed=False, detail=str(exc)), None
    return (
        SanityCheck(
            name="modes_unambiguously_tracked",
            passed=True,
            detail=(
                f"followed one mode through indices {tracked.indices}; "
                f"worst match margin {tracked.worst_margin:.4f}"
            ),
        ),
        tracked,
    )
