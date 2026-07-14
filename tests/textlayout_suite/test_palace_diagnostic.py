from __future__ import annotations

from pathlib import Path

import pytest

from textlayout.solvers.palace.backend import DEFAULT_LAYOUT
from textlayout.solvers.palace.diagnostic import run_diagnostic_multimode_catalog
from textlayout.solvers.palace.models import PalaceCapability


def test_diagnostic_solver_absence_is_honest(tmp_path: Path) -> None:
    result = run_diagnostic_multimode_catalog(
        tmp_path,
        layout_path=DEFAULT_LAYOUT,
        mesh_path=tmp_path / "missing.msh",
        fem_model_path=tmp_path / "missing.json",
        capability=PalaceCapability(unavailable_reason="test absence"),
    )
    assert result.status == "SKIPPED_SOLVER_ABSENT"
    assert result.mode_catalog is not None and result.mode_catalog.is_file()


@pytest.mark.parametrize("mode_count", [5, 11])
def test_diagnostic_rejects_unbounded_mode_counts(tmp_path: Path, mode_count: int) -> None:
    with pytest.raises(ValueError, match="between 6 and 10"):
        run_diagnostic_multimode_catalog(
            tmp_path,
            layout_path=DEFAULT_LAYOUT,
            mesh_path=tmp_path / "missing.msh",
            fem_model_path=tmp_path / "missing.json",
            capability=PalaceCapability(unavailable_reason="test absence"),
            mode_count=mode_count,
        )


def test_diagnostic_is_one_rank_only(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="one MPI rank"):
        run_diagnostic_multimode_catalog(
            tmp_path,
            layout_path=DEFAULT_LAYOUT,
            mesh_path=tmp_path / "missing.msh",
            fem_model_path=tmp_path / "missing.json",
            capability=PalaceCapability(unavailable_reason="test absence"),
            processes=2,
        )
