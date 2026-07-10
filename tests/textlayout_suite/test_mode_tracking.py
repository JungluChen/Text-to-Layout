"""Eigenmode identity survives refinement; mode *index* does not.

The failure this suite exists to prevent: a convergence study reads
``frequencies[2]`` at every mesh level, two nearby modes cross between levels,
and the study silently starts converging onto a different resonance.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from textlayout.evidence import EvidenceStatus
from textlayout.simulation.mesh_convergence import (
    MeshLevel,
    SolverIdentity,
    mesh_convergence_evidence,
)
from textlayout.simulation.mode_tracking import (
    AmbiguousModeMatch,
    MatchCriteria,
    ModeSignature,
    match_mode,
    mode_tracking_check,
    score_pair,
    track_across_levels,
)

#: A quarter-wave resonator mode: energy sits in the resonator, not the feedline.
RESONATOR = {"resonator": 0.92, "feedline": 0.05, "substrate": 0.03}
#: A feedline mode: the same regions, inverted.
FEEDLINE = {"resonator": 0.04, "feedline": 0.91, "substrate": 0.05}


def _mode(index: int, frequency: float, electric: dict[str, float], **kwargs) -> ModeSignature:
    return ModeSignature(
        index=index, frequency_ghz=frequency, electric_energy_by_region=electric, **kwargs
    )


class TestSignatureValidation:
    @pytest.mark.parametrize("bad", [0.0, -6.0, float("nan"), float("inf")])
    def test_a_non_physical_frequency_is_rejected(self, bad: float) -> None:
        with pytest.raises(ValueError, match="non-physical frequency"):
            ModeSignature(index=0, frequency_ghz=bad)


class TestScoring:
    def test_a_mode_matches_itself_perfectly(self) -> None:
        mode = _mode(0, 6.0, RESONATOR)
        score, _ = score_pair(mode, mode, MatchCriteria())
        assert score == pytest.approx(1.0)

    def test_field_overlap_separates_modes_at_the_same_frequency(self) -> None:
        """Frequency proximity alone cannot tell a crossing apart. Fields can."""
        reference = _mode(0, 6.0, RESONATOR)
        same_field = _mode(1, 6.0, RESONATOR)
        other_field = _mode(2, 6.0, FEEDLINE)
        assert score_pair(reference, same_field, MatchCriteria())[0] > score_pair(
            reference, other_field, MatchCriteria()
        )[0]

    def test_absent_observables_cast_no_vote(self) -> None:
        """A solver reporting no ports must not be penalised for silence."""
        bare_a = ModeSignature(index=0, frequency_ghz=6.0)
        bare_b = ModeSignature(index=1, frequency_ghz=6.0)
        score, components = score_pair(bare_a, bare_b, MatchCriteria())
        assert set(components) == {"frequency"}
        assert score == pytest.approx(1.0)

    def test_localization_is_reported_as_a_component(self) -> None:
        _, components = score_pair(_mode(0, 6.0, RESONATOR), _mode(1, 6.05, FEEDLINE), MatchCriteria())
        assert components["localization"] == 0.0

    def test_zero_energy_vectors_are_unusable_rather_than_similar(self) -> None:
        left = _mode(0, 6.0, {"resonator": 0.0, "feedline": 0.0})
        right = _mode(1, 6.0, RESONATOR)
        _, components = score_pair(left, right, MatchCriteria())
        assert "electric_overlap" not in components  # a null vector resembles nothing


class TestCrossingModes:
    """The case that motivates the module: modes swap frequency order."""

    def test_a_crossed_mode_is_followed_by_its_field_not_its_index(self) -> None:
        coarse = [_mode(0, 5.90, RESONATOR), _mode(1, 6.10, FEEDLINE)]
        # Refinement pushes the resonator up past the feedline: order inverts.
        fine = [_mode(0, 6.02, FEEDLINE), _mode(1, 6.06, RESONATOR)]

        tracked = track_across_levels([coarse, fine], seed_index=0)

        assert tracked.indices == [0, 1]  # index changed...
        assert tracked.frequencies_ghz == [5.90, 6.06]  # ...identity did not
        assert tracked.crossed is True

    def test_reading_a_fixed_index_would_have_taken_the_wrong_mode(self) -> None:
        """Documents precisely what the naive study gets wrong."""
        coarse = [_mode(0, 5.90, RESONATOR), _mode(1, 6.10, FEEDLINE)]
        fine = [_mode(0, 6.02, FEEDLINE), _mode(1, 6.06, RESONATOR)]
        naive = [level[0].frequency_ghz for level in (coarse, fine)]
        tracked = track_across_levels([coarse, fine], seed_index=0)
        assert naive == [5.90, 6.02]  # the feedline mode, mislabelled
        assert tracked.frequencies_ghz == [5.90, 6.06]

    def test_a_wholesale_reordering_is_followed(self) -> None:
        """An extra mode entering the window shifts every index."""
        coarse = [_mode(0, 5.90, RESONATOR), _mode(1, 6.40, FEEDLINE)]
        fine = [
            _mode(0, 5.20, {"package": 0.95, "resonator": 0.05}),  # new spurious mode
            _mode(1, 5.92, RESONATOR),
            _mode(2, 6.41, FEEDLINE),
        ]
        tracked = track_across_levels([coarse, fine], seed_index=0)
        assert tracked.indices == [0, 1]
        assert tracked.frequencies_ghz[-1] == 5.92

    def test_tracking_across_three_levels_accumulates_matches(self) -> None:
        levels = [
            [_mode(0, 5.90, RESONATOR), _mode(1, 6.30, FEEDLINE)],
            [_mode(0, 6.02, FEEDLINE), _mode(1, 5.96, RESONATOR)],
            [_mode(0, 5.98, RESONATOR), _mode(1, 6.01, FEEDLINE)],
        ]
        tracked = track_across_levels(levels, seed_index=0)
        assert tracked.frequencies_ghz == [5.90, 5.96, 5.98]
        assert len(tracked.matches) == 2
        assert tracked.worst_margin > 0


class TestAmbiguityIsRejectedNotGuessed:
    def test_degenerate_modes_refuse_to_be_tracked(self) -> None:
        """Two identical modes at the same frequency cannot be told apart."""
        coarse = [_mode(0, 6.00, RESONATOR)]
        fine = [_mode(0, 6.00, RESONATOR), _mode(1, 6.00, RESONATOR)]
        with pytest.raises(AmbiguousModeMatch, match="indistinguishable within margin"):
            track_across_levels([coarse, fine], seed_index=0)

    def test_a_vanished_mode_is_not_substituted_by_the_nearest_survivor(self) -> None:
        coarse = [_mode(0, 6.00, RESONATOR)]
        fine = [_mode(0, 9.00, {"package": 0.99})]
        with pytest.raises(AmbiguousModeMatch, match="was not found in this level"):
            track_across_levels([coarse, fine], seed_index=0)

    def test_a_non_mutual_assignment_is_rejected(self) -> None:
        """Two references may not both claim one candidate."""
        criteria = MatchCriteria(margin=0.0, min_score=0.0)
        coarse = [_mode(0, 6.00, RESONATOR), _mode(1, 6.01, RESONATOR)]
        fine = [_mode(0, 6.005, RESONATOR)]
        with pytest.raises(AmbiguousModeMatch, match="not mutual|indistinguishable"):
            track_across_levels([coarse, fine], seed_index=1, criteria=criteria)

    def test_the_margin_is_configurable(self) -> None:
        coarse = [_mode(0, 6.00, RESONATOR)]
        fine = [_mode(0, 6.00, RESONATOR), _mode(1, 6.001, RESONATOR)]
        with pytest.raises(AmbiguousModeMatch):
            track_across_levels([coarse, fine], seed_index=0)
        # A study that has independently established these are distinct may say so.
        tracked = track_across_levels(
            [coarse, fine], seed_index=0, criteria=MatchCriteria(margin=0.0)
        )
        assert tracked.indices == [0, 0]

    def test_the_reported_margin_exposes_a_shaky_chain(self) -> None:
        levels = [
            [_mode(0, 6.00, RESONATOR), _mode(1, 6.20, FEEDLINE)],
            [_mode(0, 6.01, RESONATOR), _mode(1, 6.19, FEEDLINE)],
        ]
        tracked = track_across_levels(levels, seed_index=0)
        assert 0.0 < tracked.worst_margin <= 1.0


class TestSeeding:
    def test_seed_by_frequency_picks_the_nearest_mode(self) -> None:
        levels = [
            [_mode(0, 4.00, FEEDLINE), _mode(1, 6.00, RESONATOR)],
            [_mode(0, 4.01, FEEDLINE), _mode(1, 6.02, RESONATOR)],
        ]
        tracked = track_across_levels(levels, seed_frequency_ghz=6.05)
        assert tracked.frequencies_ghz == [6.00, 6.02]

    def test_exactly_one_seed_is_required(self) -> None:
        levels = [[_mode(0, 6.0, RESONATOR)], [_mode(0, 6.0, RESONATOR)]]
        with pytest.raises(ValueError, match="exactly one of seed_index"):
            track_across_levels(levels)
        with pytest.raises(ValueError, match="exactly one of seed_index"):
            track_across_levels(levels, seed_index=0, seed_frequency_ghz=6.0)

    def test_an_unknown_seed_index_is_an_error(self) -> None:
        levels = [[_mode(0, 6.0, RESONATOR)], [_mode(0, 6.0, RESONATOR)]]
        with pytest.raises(ValueError, match="no mode with index 7"):
            track_across_levels(levels, seed_index=7)

    def test_tracking_needs_at_least_two_levels(self) -> None:
        with pytest.raises(ValueError, match="at least two refinement levels"):
            track_across_levels([[_mode(0, 6.0, RESONATOR)]], seed_index=0)

    def test_an_empty_level_is_an_error(self) -> None:
        with pytest.raises(ValueError, match="at least one mode"):
            track_across_levels([[_mode(0, 6.0, RESONATOR)], []], seed_index=0)


class TestMatchMode:
    def test_no_candidates_is_ambiguous_not_silent(self) -> None:
        with pytest.raises(AmbiguousModeMatch, match="no candidate modes"):
            match_mode(_mode(0, 6.0, RESONATOR), [])

    def test_a_lone_candidate_has_a_zero_runner_up(self) -> None:
        match = match_mode(_mode(0, 6.0, RESONATOR), [_mode(3, 6.01, RESONATOR)])
        assert match.matched_index == 3
        assert match.runner_up_score == 0.0
        assert match.margin == match.score

    def test_components_are_retained_for_audit(self) -> None:
        match = match_mode(
            _mode(0, 6.0, RESONATOR, port_participation={"p1": 0.8}),
            [_mode(1, 6.01, RESONATOR, port_participation={"p1": 0.79})],
        )
        assert {"frequency", "electric_overlap", "localization", "port_participation"} <= set(
            match.components
        )


class TestTrackingGatesTheEvidenceLadder:
    """An untrackable mode makes a convergence study meaningless, not merely noisy."""

    TRACKABLE = [
        [_mode(0, 5.90, RESONATOR), _mode(1, 6.40, FEEDLINE)],
        [_mode(0, 6.30, FEEDLINE), _mode(1, 5.96, RESONATOR)],
        [_mode(0, 5.97, RESONATOR), _mode(1, 6.28, FEEDLINE)],
    ]
    DEGENERATE = [
        [_mode(0, 6.00, RESONATOR)],
        [_mode(0, 6.00, RESONATOR), _mode(1, 6.00, RESONATOR)],
        [_mode(0, 6.00, RESONATOR)],
    ]

    def _evidence(self, tmp_path: Path, levels, tracking_check):
        outputs = []
        for index in range(3):
            path = tmp_path / f"level{index}.csv"
            path.write_text("f_GHz\n6.0\n", encoding="utf-8")
            outputs.append(path)
        mesh_levels = [
            MeshLevel(characteristic_length_um=lc, frequency_ghz=f, output_file=out)
            for lc, f, out in zip([20.0, 10.0, 5.0], levels, outputs)
        ]
        return mesh_convergence_evidence(
            design_id="cpw_resonator",
            design_hash="d" * 64,
            component="quarter_wave_resonator",
            analysis_scope="resonator_eigenmode",
            levels=mesh_levels,
            solver=SolverIdentity(name="Palace", version="0.13.0", container_digest="sha256:" + "c" * 64),
            threshold_percent=1.0,
            extra_checks=[tracking_check],
            output_root=tmp_path,
            timestamp="2026-07-10T00:00:00+00:00",
        )

    def test_a_trackable_mode_passes_the_check_and_reaches_simulation_executed(
        self, tmp_path: Path
    ) -> None:
        check, tracked = mode_tracking_check(self.TRACKABLE, seed_index=0)
        assert check.passed and tracked is not None
        assert tracked.crossed is True
        record = self._evidence(tmp_path, tracked.frequencies_ghz, check)
        assert record.status is EvidenceStatus.SIMULATION_EXECUTED
        assert record.extracted_value == 5.97

    def test_an_ambiguous_mode_makes_the_study_simulation_invalid(self, tmp_path: Path) -> None:
        check, tracked = mode_tracking_check(self.DEGENERATE, seed_index=0)
        assert not check.passed and tracked is None
        # The frequencies look perfectly converged -- 6.0 at every level. They are
        # not measurements of the same mode, so the study earns nothing.
        record = self._evidence(tmp_path, [6.0, 6.0, 6.0], check)
        assert record.status is EvidenceStatus.SIMULATION_INVALID
        assert record.extracted_value is None
        assert "modes_unambiguously_tracked" in (record.invalidation_reason or "")

    def test_the_tracking_check_is_recorded_by_name_either_way(self, tmp_path: Path) -> None:
        check, tracked = mode_tracking_check(self.TRACKABLE, seed_index=0)
        assert tracked is not None
        record = self._evidence(tmp_path, tracked.frequencies_ghz, check)
        assert "modes_unambiguously_tracked" in {c.name for c in record.sanity_checks}
