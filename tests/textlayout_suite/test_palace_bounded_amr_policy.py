import pytest
from pydantic import ValidationError

from textlayout.solvers.palace.benchmark_v017 import AMRSettings
from textlayout.solvers.palace.models import PalaceBoundedAMRPolicy


@pytest.mark.parametrize(
    ("states", "refinements"),
    [(1, 0), (2, 1), (3, 2)],
)
def test_bounded_amr_counts_useful_refinements(states: int, refinements: int) -> None:
    policy = PalaceBoundedAMRPolicy(solved_states=states)
    assert policy.effective_refinement_count == refinements
    assert policy.adapted_mesh_count == refinements
    config = AMRSettings(bounded_policy=policy).refinement_config()
    assert config["MaxIts"] == refinements
    assert config["SaveAdaptMesh"] is False


def test_bounded_amr_final_mesh_must_be_requested_explicitly() -> None:
    policy = PalaceBoundedAMRPolicy(
        solved_states=2,
        refinement_count=2,
        perform_adaptation_after_final_solve=True,
        retain_final_adapted_mesh=True,
        save_final_mesh=True,
    )
    assert policy.saved_mesh_count == 1
    assert policy.refinement_config()["SaveAdaptMesh"] is True


def test_bounded_amr_final_mesh_is_disabled_by_default() -> None:
    policy = PalaceBoundedAMRPolicy(solved_states=2)
    assert policy.saved_mesh_count == 0
    assert policy.refinement_config()["SaveAdaptMesh"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {"solved_states": -1},
        {"solved_states": 2, "refinement_count": -1},
        {"solved_states": 2, "refinement_count": 2},
        {"solved_states": 2, "perform_adaptation_after_final_solve": True},
    ],
)
def test_bounded_amr_rejects_invalid_counts(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        PalaceBoundedAMRPolicy(**payload)
